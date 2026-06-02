const tg = window.Telegram.WebApp;

tg.ready();
tg.expand();

const API_BASE = "";

let cart = [];

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
        const response = await fetch(`${API_BASE}/api/products`);
        if (!response.ok) {
            throw new Error('Не удалось загрузить товары с сервера');
        }

        const products = await response.json();

        document.getElementById('pizza-section').innerHTML = '';
        document.getElementById('sushi-section').innerHTML = '';
        document.getElementById('drinks-section').innerHTML = '';

        if (products.length === 0) {
            const emptyMsg = "<p class='hint-text' style='text-align:center; padding:20px;'>Меню временно пусто. Добавьте товары в БД!</p>";
            document.getElementById('pizza-section').innerHTML = emptyMsg;
            return;
        }

        products.forEach(product => {
            const cardHtml = `
                <div class="food-card">
                    <div class="food-info">
                        <h3>${product.name}</h3>
                        <p class="hint-text">${product.description || ''}</p>
                        <span class="price">${product.price} Stars</span>
                    </div>
                    <button class="add-btn" onclick="addToCart(${product.id}, ${product.price})">Добавить</button>
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

function addToCart(itemId, price) {
    cart.push({ id: itemId, price: price });

    const totalSum = cart.reduce((sum, item) => sum + item.price, 0);

    tg.MainButton.text = `Оформить заказ (${totalSum} Stars)`;
    if (!tg.MainButton.isVisible) {
        tg.MainButton.show();
    }

    if (tg.HapticFeedback) {
        tg.HapticFeedback.notificationOccurred('success');
    }
}

async function addToCart(itemId, price) {
    cart.push({ id: itemId, price: price });

    const totalSum = cart.reduce((sum, item) => sum + item.price, 0);
    const buttonText = `Оформить заказ (${totalSum} Stars)`;

    // Проверяем, открыты ли мы внутри Телеграма
    if (tg.initData === "") {
        // Мы в обычном браузере на ПК — показываем нашу HTML кнопку
        const browserBtn = document.getElementById('browser-cart-btn');
        if (browserBtn) {
            browserBtn.innerText = buttonText;
            browserBtn.style.display = 'block';
        }
    } else {
        // Мы внутри Telegram — управляем нативной кнопкой
        tg.MainButton.text = buttonText;
        if (!tg.MainButton.isVisible) {
            tg.MainButton.show();
        }
    }

    if (tg.HapticFeedback) {
        tg.HapticFeedback.notificationOccurred('success');
    }
}

async function handleCheckout() {
    let userId = tg.initDataUnsafe?.user?.id;

    // Костыль для тестов: если открыто в браузере, ставим фейковый ID, чтобы бэкенд не ругался
    if (!userId) {
        if (tg.initData === "") {
            userId = 6263303676; // Твой ID для тестов в браузере
        } else {
            tg.showAlert("Ошибка: Данные пользователя Telegram не найдены.");
            return;
        }
    }

    if (cart.length === 0) {
        alert("Ваша корзина пуста!");
        return;
    }

    if (tg.MainButton.isVisible) tg.MainButton.showProgress();

    try {
        const response = await fetch(`${API_BASE}/api/orders`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                userId: parseInt(userId),
                items: cart
            })
        });

        if (!response.ok) {
            throw new Error('Ошибка создания заказа на сервере');
        }

        const data = await response.json();

        if (data.redirect_url) {
            if (tg.initData !== "") {
                // Если в ТГ — используем нативный переход
                tg.openTelegramLink(data.redirect_url);
                tg.close();
            } else {
                // Если в браузере ПК — просто выводим ссылку в консоль или переходим по ней
                console.log("Ссылка на оплату заказа:", data.redirect_url);
                alert(`Заказ создан! Ссылка на оплату отправлена в консоль (F12). URL: ${data.redirect_url}`);
                window.location.href = data.redirect_url;
            }
        } else {
            alert("Заказ создан, но ссылка на оплату не получена.");
        }
    } catch (error) {
        console.error("Ошибка при оформлении заказа:", error);
        alert("Не удалось отправить заказ. Проверьте консоль бэкенда.");
    } finally {
        if (tg.MainButton.isVisible) tg.MainButton.hideProgress();
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

    tg.MainButton.onClick(handleCheckout);

    loadMenu();
}

document.addEventListener('DOMContentLoaded', initApp);