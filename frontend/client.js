const socket = io(window.location.origin);
 
const statusEl = document.getElementById('status');
const messagesEl = document.getElementById('messages');

const textInput = document.getElementById('text');

const sendBtn = document.getElementById('send');
const reloadBtn = document.getElementById('reload');

// Элементы аутентификации
const authContainer = document.getElementById('auth-container');
const userInfoDiv = document.getElementById('user-info');
const currentUserSpan = document.getElementById('current-user');
const logoutBtn = document.getElementById('logout-btn');
const deleteAccountBtn = document.getElementById('delete-account-btn');
const chatContainer = document.getElementById('chat-container');

// Вкладки
const tabBtns = document.querySelectorAll('.tab-btn');
const loginForm = document.getElementById('login-form');
const registerForm = document.getElementById('register-form');

// Поля входа
const loginEmail = document.getElementById('login-email');
const loginPassword = document.getElementById('login-password');
const loginBtn = document.getElementById('login-btn');
const loginEmailError = document.getElementById('login-email-error');
const loginPasswordError = document.getElementById('login-password-error');

// Поля регистрации
const regEmail = document.getElementById('reg-email');
const regName = document.getElementById('reg-name');
const regPhone = document.getElementById('reg-phone');
const regPassword = document.getElementById('reg-password');
const regPassword2 = document.getElementById('reg-password2');
const registerBtn = document.getElementById('register-btn');
const regEmailError = document.getElementById('reg-email-error');
const regNameError = document.getElementById('reg-name-error');
const regPhoneError = document.getElementById('reg-phone-error');
const regPasswordError = document.getElementById('reg-password-error');
const regPassword2Error = document.getElementById('reg-password2-error');

// Диалог подтверждения
const verifyDialog = document.getElementById('verify-dialog');
const verifyEmailSpan = document.getElementById('verify-email');
const verifyCode = document.getElementById('verify-code');
const verifyBtn = document.getElementById('verify-btn');
const resendCodeBtn = document.getElementById('resend-code');
const cancelVerifyBtn = document.getElementById('cancel-verify');

let currentUser = null;

// ========== Валидация ==========
function validateEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

function validatePhone(phone) {
    if (!phone) return true;
    // Удаляем все пробелы, дефисы, скобки
    const cleaned = phone.replace(/[\s\-\(\)]/g, '');
    const re = /^\+?[0-9]{10,15}$/;
    return re.test(cleaned);
}

function validateName(name) {
    if (!name) return true;
    return name.trim().length > 0;
}

function validatePassword(password) {
    return password.length >= 6;
}

function validatePasswordMatch(p1, p2) {
    return p1 === p2;
}

// Функции для обновления ошибок на форме входа
function validateLoginForm() {
    let isValid = true;

    if (!validateEmail(loginEmail.value.trim())) {
        loginEmailError.textContent = 'Некорректный email. Пример: user@example.com';
        loginEmail.classList.add('error-border');
        isValid = false;
    } else {
        loginEmailError.textContent = '';
        loginEmail.classList.remove('error-border');
    }

    if (!validatePassword(loginPassword.value)) {
        loginPasswordError.textContent = 'Пароль должен быть не менее 6 символов';
        loginPassword.classList.add('error-border');
        isValid = false;
    } else {
        loginPasswordError.textContent = '';
        loginPassword.classList.remove('error-border');
    }

    return isValid;
}

// Функции для обновления ошибок на форме регистрации
function validateRegisterForm() {
    let isValid = true;

    // Email
    if (!validateEmail(regEmail.value.trim())) {
        regEmailError.textContent = 'Некорректный email. Пример: user@example.com';
        regEmail.classList.add('error-border');
        isValid = false;
    } else {
        regEmailError.textContent = '';
        regEmail.classList.remove('error-border');
    }

    // Имя
    if (regName.value.trim() && !validateName(regName.value)) {
        regNameError.textContent = 'Имя не может быть пустым';
        regName.classList.add('error-border');
        isValid = false;
    } else {
        regNameError.textContent = '';
        regName.classList.remove('error-border');
    }

    // Телефон
    if (regPhone.value.trim() && !validatePhone(regPhone.value.trim())) {
        regPhoneError.textContent = 'Телефон должен содержать 10-15 цифр, может начинаться с +. Пример: 79123456789';
        regPhone.classList.add('error-border');
        isValid = false;
    } else {
        regPhoneError.textContent = '';
        regPhone.classList.remove('error-border');
    }

    // Пароль
    if (!validatePassword(regPassword.value)) {
        regPasswordError.textContent = 'Пароль должен быть не менее 6 символов';
        regPassword.classList.add('error-border');
        isValid = false;
    } else {
        regPasswordError.textContent = '';
        regPassword.classList.remove('error-border');
    }

    // Подтверждение пароля
    if (!validatePasswordMatch(regPassword.value, regPassword2.value)) {
        regPassword2Error.textContent = 'Пароли не совпадают';
        regPassword2.classList.add('error-border');
        isValid = false;
    } else {
        regPassword2Error.textContent = '';
        regPassword2.classList.remove('error-border');
    }

    return isValid;
}

// Подписка на события ввода
loginEmail.addEventListener('input', validateLoginForm);
loginPassword.addEventListener('input', validateLoginForm);

regEmail.addEventListener('input', validateRegisterForm);
regName.addEventListener('input', validateRegisterForm);
regPhone.addEventListener('input', validateRegisterForm);
regPassword.addEventListener('input', validateRegisterForm);
regPassword2.addEventListener('input', validateRegisterForm);

// ========== Общие функции ==========
function setStatus(type, msg) {
    statusEl.className = type;
    statusEl.textContent = msg;
}

function escapeHtml(str) {
    return String(str).replace(/[&<>"]/g, function(match) {
        if (match === '&') return '&amp;';
        if (match === '<') return '&lt;';
        if (match === '>') return '&gt;';
        if (match === '"') return '&quot;';
        return match;
    });
}

function displayMessage(msg) {
    try {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'msg';
        const meta = document.createElement('div');
        meta.className = 'meta';
        const sender = msg.sender?.name || msg.sender?.email || msg.senderId || 'Неизвестно';
        const time = msg.createdAt ? new Date(msg.createdAt).toLocaleString() : '';
        meta.textContent = `${escapeHtml(sender)} • ${time}`;
        const textDiv = document.createElement('div');
        textDiv.textContent = msg.text;
        msgDiv.appendChild(meta);
        msgDiv.appendChild(textDiv);
        messagesEl.appendChild(msgDiv);
    } catch (e) {
        console.error('displayMessage error:', e);
    }
}

// ========== Загрузка сообщений ==========
async function loadMessages() {
    try {
        const res = await fetch('/messages?take=200');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (!Array.isArray(data)) throw new Error('Сервер вернул не массив');
        messagesEl.innerHTML = '';
        data.forEach(displayMessage);
        messagesEl.scrollTop = messagesEl.scrollHeight;
    } catch (e) {
        setStatus('error', 'Ошибка загрузки: ' + e.message);
    }
}

// ========== Аутентификация ==========

// Переключение вкладок
tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        tabBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        if (btn.dataset.tab === 'login') {
            loginForm.classList.add('active');
            registerForm.classList.remove('active');
        } else {
            loginForm.classList.remove('active');
            registerForm.classList.add('active');
        }
    });
});

// Проверка статуса при загрузке
async function checkAuthStatus() {
    try {
        const res = await fetch('/auth/status');
        const data = await res.json();
        if (data.authenticated) {
            currentUser = data.user;
            showAuthenticatedUI();
        } else {
            showUnauthenticatedUI();
        }
    } catch (e) {
        console.error('Ошибка проверки статуса:', e);
    }
}

function showAuthenticatedUI() {
    authContainer.style.display = 'none';
    userInfoDiv.style.display = 'flex';
    currentUserSpan.textContent = `${currentUser.name || currentUser.email} (${currentUser.email})`;
    chatContainer.style.display = 'block';
    loadMessages();
}

function showUnauthenticatedUI() {
    authContainer.style.display = 'block';
    userInfoDiv.style.display = 'none';
    chatContainer.style.display = 'none';
    messagesEl.innerHTML = '';
}

// Регистрация
registerBtn.addEventListener('click', async () => {
    // Очищаем предыдущие ошибки
    [regEmailError, regNameError, regPhoneError, regPasswordError, regPassword2Error].forEach(el => {
        if (el) el.textContent = '';
    });
    [regEmail, regName, regPhone, regPassword, regPassword2].forEach(el => {
        if (el) el.classList.remove('error-border');
    });

    if (!validateRegisterForm()) {
        setStatus('error', 'Исправьте ошибки в форме');
        return;
    }

    const email = regEmail.value.trim();
    const password = regPassword.value;
    const name = regName.value.trim() || undefined;
    const phone = regPhone.value.trim() ? regPhone.value.replace(/[\s\-\(\)]/g, '') : undefined;

    try {
        const res = await fetch('/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password, name, phone })
        });
        const data = await res.json();

        if (!res.ok) {
            // Обработка структурированных ошибок от express-validator
            if (data.errors && Array.isArray(data.errors)) {
                data.errors.forEach(err => {
                    const field = err.param;
                    const msg = err.msg;
                    if (field === 'email') {
                        regEmailError.textContent = msg;
                        regEmail.classList.add('error-border');
                    } else if (field === 'phone') {
                        regPhoneError.textContent = msg;
                        regPhone.classList.add('error-border');
                    } else if (field === 'password') {
                        regPasswordError.textContent = msg;
                        regPassword.classList.add('error-border');
                    } else if (field === 'name') {
                        regNameError.textContent = msg;
                        regName.classList.add('error-border');
                    }
                });
                setStatus('error', 'Проверьте поля с ошибками');
            }
            // Обработка простой текстовой ошибки (например, дубликат)
            else if (data.error) {
                const errorMsg = data.error.toLowerCase();
                if (errorMsg.includes('email')) {
                    regEmailError.textContent = data.error;
                    regEmail.classList.add('error-border');
                } else if (errorMsg.includes('телефон')) {
                    regPhoneError.textContent = data.error;
                    regPhone.classList.add('error-border');
                } else {
                    setStatus('error', data.error);
                }
            } else {
                setStatus('error', 'Ошибка регистрации');
            }
            return;
        }

        // Успех – показываем диалог подтверждения
        verifyEmailSpan.textContent = email;
        verifyDialog.style.display = 'flex';
        setStatus('ok', 'Код отправлен на email');
    } catch (e) {
        setStatus('error', e.message);
    }
});

// Подтверждение кода
verifyBtn.addEventListener('click', async () => {
    const code = verifyCode.value.trim();
    const email = verifyEmailSpan.textContent;
    if (!code) {
        setStatus('error', 'Введите код');
        return;
    }
    try {
        const res = await fetch('/auth/verify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, code })
        });
        const data = await res.json();

        if (!res.ok) {
            throw new Error(data.error || 'Ошибка подтверждения');
        }

        // Успешное подтверждение – автоматический вход
        currentUser = data.user;
        verifyDialog.style.display = 'none';
        showAuthenticatedUI();
        setStatus('ok', 'Регистрация прошла успешно! Добро пожаловать!');
    } catch (e) {
        setStatus('error', e.message);
    }
});

// Повторная отправка кода
resendCodeBtn.addEventListener('click', async () => {
    const email = verifyEmailSpan.textContent;
    try {
        const res = await fetch('/auth/resend-code', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error);
        setStatus('ok', 'Код отправлен повторно');
    } catch (e) {
        setStatus('error', e.message);
    }
});

// Отмена диалога
cancelVerifyBtn.addEventListener('click', () => {
    verifyDialog.style.display = 'none';
    verifyCode.value = '';
});

// Вход
loginBtn.addEventListener('click', async () => {
    if (!validateLoginForm()) {
        setStatus('error', 'Исправьте ошибки в форме');
        return;
    }

    const email = loginEmail.value.trim();
    const password = loginPassword.value;

    try {
        const res = await fetch('/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });
        const data = await res.json();
        if (!res.ok) {
            if (res.status === 403 && data.needsVerification) {
                verifyEmailSpan.textContent = data.email;
                verifyDialog.style.display = 'flex';
                setStatus('error', data.error);
            } else {
                throw new Error(data.error || 'Ошибка входа');
            }
            return;
        }
        currentUser = data.user;
        showAuthenticatedUI();
        setStatus('ok', 'Вход выполнен');
    } catch (e) {
        setStatus('error', e.message);
    }
});

// Выход
logoutBtn.addEventListener('click', async () => {
    try {
        const res = await fetch('/auth/logout', { method: 'POST' });
        if (!res.ok) throw new Error('Ошибка выхода');
        showUnauthenticatedUI();
        setStatus('ok', 'Вы вышли');
    } catch (e) {
        setStatus('error', e.message);
    }
});

// Удаление аккаунта
deleteAccountBtn.addEventListener('click', async () => {
    if (!confirm('Вы уверены, что хотите удалить аккаунт? Все сообщения будут безвозвратно удалены.')) return;
    try {
        const res = await fetch('/auth/account', { method: 'DELETE' });
        if (!res.ok) throw new Error('Ошибка удаления');
        showUnauthenticatedUI();
        setStatus('ok', 'Аккаунт удалён');
    } catch (e) {
        setStatus('error', e.message);
    }
});

// ========== Отправка сообщений ==========
sendBtn.addEventListener('click', sendMessage);
textInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') sendMessage();
});

async function sendMessage() {
    const text = textInput.value.trim();
    if (!text) return;
    try {
        const res = await fetch('/messages', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text })
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.error || 'Ошибка отправки');
        }
        textInput.value = '';
    } catch (e) {
        setStatus('error', e.message);
    }
}

// ========== WebSocket ==========
socket.on('new_message', (msg) => {
    displayMessage(msg);
    messagesEl.scrollTop = messagesEl.scrollHeight;
});
 
reloadBtn.addEventListener('click', loadMessages);
 
// Инициализация
checkAuthStatus();
