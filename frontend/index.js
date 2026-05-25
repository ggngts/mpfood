const tg = window.Telegram.WebApp;

tg.ready();
tg.expand();

let cart = [];

tg.MainButton.text = "Оформить заказ";

function switchTab(event, sectionId) {
    const contents = document.querySelectorAll('.tab-content');
    contents.forEach(content => content.classList.remove('active'));

    const buttons = document.querySelectorAll('.tab-btn');
    buttons.forEach(button => button.classList.remove('active'));

    document.getElementById(sectionId).classList.add('active');
    event.currentTarget.classList.add('active');
    
    if (tg.HapticFeedback) {
        tg.HapticFeedback.impactOccurred('light');
    }
}

async function loadMenu() {
    try {
        const response = await fetch('/api/products');
        if (!response.ok) {
            throw new Error('Не удалось загрузить товары с сервера');
        }
        
        const products = await response.json();

        document.getElementById('pizza-section').innerHTML = '';
        document.getElementById('sushi-section').innerHTML = '';
        document.getElementById('drinks-section').innerHTML = '';

        products.forEach(product => {
            const cardHtml = `
                <div class="food-card">
                    <div class="food-info">
                        <h3>${product.name}</h3>
                        <p class="hint-text">${product.description}</p>
                        <span class="price">${product.price} ₽</span>
                    </div>
                    <button class="add-btn" onclick="addToCart('${product.id}', ${product.price})">Добавить</button>
                </div>
            `;

            if (product.category === 'pizza') {
                document.getElementById('pizza-section').innerHTML += cardHtml;
            } else if (product.category === 'sushi') {
                document.getElementById('sushi-section').innerHTML += cardHtml;
            } else if (product.category === 'drinks') {
                document.getElementById('drinks-section').innerHTML += cardHtml;
            }
        });

    } catch (error) {
        console.error("Ошибка загрузки меню:", error);
        tg.showAlert("Ошибка при загрузке меню из базы данных. Проверьте работу API.");
    }
}

function initApp() {
    const user = tg.initDataUnsafe?.user;
    if (user) {
        const userNameElement = document.getElementById('username');
        if (userNameElement) {
            userNameElement.innerText = user.first_name || 'Гурман';
        }
    }

    loadMenu();
}

function addToCart(itemId, price) {
    cart.push({ id: itemId, price: price });
    
    const totalSum = cart.reduce((sum, item) => sum + item.price, 0);

    tg.MainButton.text = `Оформить заказ (${totalSum} ₽)`;
    if (!tg.MainButton.isVisible) {
        tg.MainButton.show();
    }

    if (tg.HapticFeedback) {
        tg.HapticFeedback.notificationOccurred('success');
    }
}

async function handleCheckout() {
    try {
        await axios.post('/api/orders/initiate', {
            items: cart.items,
            user_id: window.Telegram?.WebApp?.initDataUnsafe?.user?.id
        });

        if (window.Telegram?.WebApp) {
            window.Telegram.WebApp.close();
        }
    } catch (error) {
        console.error("Ошибка при оформлении:", error);
    }
}


// Пример функции отправки заказа на фронтенде
async function sendOrder() {
    const response = await fetch('/api/orders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(yourOrderData)
    });

    const data = await response.json();

    if (data.redirect_url) {
        // Проверяем, открыто ли приложение ВНУТРИ Telegram (как Mini App)
        if (window.Telegram && window.Telegram.WebApp) {
            // Используем встроенный метод Mini App для безопасного перехода
            window.Telegram.WebApp.openTelegramLink(data.redirect_url);
        } else {
            // Если открыто в обычном браузере на ПК/телефоне, просто редиректим
            window.location.href = data.redirect_url;
        }
    }
}

const orderId = response.order_id;

const botLink = `https://t.me/mpfoodorderbot?start=order_${orderId}`;

Telegram.WebApp.openTelegramLink(botLink);

Telegram.WebApp.close();


document.addEventListener('DOMContentLoaded', initApp);
