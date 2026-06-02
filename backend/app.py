import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict
from typing import List
from sqlalchemy.orm import Session

from backend.db import SessionLocal, engine, Base, get_db
from backend.models import Product, Order, OrderItem

load_dotenv()

Base.metadata.create_all(bind=engine)

app = FastAPI(title="MPFood API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ProductSchema(BaseModel):
    id: str
    name: str
    description: str | None = None
    price: float
    category: str

    model_config = ConfigDict(from_attributes=True)


class CartItem(BaseModel):
    id: str
    price: float


class OrderCreate(BaseModel):
    userId: int
    items: List[CartItem]


@app.get("/api")
def read_root():
    return {"status": "running", "project": "MPFood API"}


@app.get("/api/products", response_model=List[ProductSchema])
def get_all_products(db: Session = Depends(get_db)):
    return db.query(Product).filter(Product.is_available == True).all()


@app.post("/api/products", response_model=ProductSchema)
def create_product(product: ProductSchema, db: Session = Depends(get_db)):
    db_product = db.query(Product).filter(Product.id == product.id).first()
    if db_product:
        raise HTTPException(status_code=400, detail="Товар с таким ID уже существует")

    new_product = Product(
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

    redirect_url = f"https://t.me/mpfoodorderbot?start=order_{new_order.id}"

    return {
        "status": "success",
        "order_id": new_order.id,
        "total_price": float(new_order.total_price),
        "redirect_url": redirect_url
    }