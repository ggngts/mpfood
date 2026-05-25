import os
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from typing import List
from sqlalchemy import func, create_engine, Column, Integer, BigInteger, Numeric, String, ForeignKey, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, declarative_base, relationship
import uuid
import httpx
import json
import redis.asyncio as aioredis
from backend.db import SessionLocal, Order, engine, Base
from backend.models import Order, OrderItem
load_dotenv()

redis_client = aioredis.from_url("redis://localhost:6379", decode_responses=True)
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN = 6263303676
bot_notification = Bot(token=BOT_TOKEN) if BOT_TOKEN else None

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()




class ProductDB(Base):
    __tablename__ = "products"

    id = Column(String(50), primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Integer, nullable=False)
    category = Column(String(50), nullable=False)


Base.metadata.create_all(bind=engine)


app = FastAPI(title="MPFood API")


class ProductSchema(BaseModel):
    id: str
    name: str
    description: str | None = None
    price: int
    category: str

    class Config:
        from_attributes = True

class CartItem(BaseModel):
    id: str
    price: int

class OrderSchema(BaseModel):
    items: List[CartItem]
    userId: int | None = None

class OrderItemCreate(BaseModel):
    id: str
    price: float
    quantity: int = 1

class OrderCreate(BaseModel):
    userId: int
    items: List[OrderItemCreate]

    model_config = ConfigDict(from_attributes=True)






def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/api")
def read_root():
    return {"status": "running", "project": "MPFood API"}

@app.get("/api/products", response_model=List[ProductSchema])
def get_all_products(db: Session = Depends(get_db)):
    products = db.query(ProductDB).all()
    return products

@app.post("/api/products", response_model=ProductSchema)
def create_product(product: ProductSchema, db: Session = Depends(get_db)):
    db_product = db.query(ProductDB).filter(ProductDB.id == product.id).first()
    if db_product:
        raise HTTPException(status_code=400, detail="Товар с таким ID уже существует")
    
    new_product = ProductDB(
        id=product.id,
        name=product.name,
        description=product.description,
        price=product.price,
        category=product.category
    )
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    return new_product


@app.post("/api/orders", status_code=status.HTTP_201_CREATED)
async def create_order(payload: OrderCreate, db: Session = Depends(get_db)):
    if not payload.items:
        raise HTTPException(status_code=400, detail="Корзина пуста")

    total_price = sum(item.price for item in payload.items)

    new_order = Order(
        user_id=payload.userId,
        total_price=total_price,
        status="pending"
    )
    db.add(new_order)
    db.flush()

    grouped_items = {}
    for item in payload.items:
        if item.id not in grouped_items:
            grouped_items[item.id] = {"quantity": 0, "price": item.price}
        grouped_items[item.id]["quantity"] += 1

    for prod_id, info in grouped_items.items():
        order_item = OrderItem(
            order_id=new_order.id,
            product_id=prod_id,
            quantity=info["quantity"],
            price=info["price"]
        )
        db.add(order_item)

    db.commit()
    db.refresh(new_order)

    return {
        "status": "success",
        "order_id": new_order.id,
        "total_price": float(new_order.total_price)
    }

    redirect_url = f"https://t.me/mpfoodorderbot?start=order_{new_order.id}"

    return {
        "status": "success",
        "message": "Order created",
        "redirect_url": redirect_url
    }


@app.post("/api/orders/initiate")
async def initiate_order(data: OrderCreate, db: Session = Depends(get_db)):

    text = (
        f"🛒 <b>Ваша корзина готова к оплате!</b>\n\n"
        f"📋 <b>Состав заказа:</b>\n"
    )

    for item in data.items:
        text += f"▪️ {item.name} x {item.quantity} шт. — <code>{item.price}</code> XTR\n"

    text += f"\n💰 <b>Итого к оплате:</b> <code>{data.total_price}</code> Stars"

    buttons = [
        [
            InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel:{data.id}"),
            InlineKeyboardButton(text="💳 Оплатить", callback_data=f"pay:{data.id}:{int(data.total_price)}")
        ]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await bot_notification.send_message(
        chat_id=data.userId,
        text=text,
        parse_mode="HTML",
        reply_markup=keyboard
    )

    return {"status": "success", "order_id": data.id}

    
