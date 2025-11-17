
import json, logging, os
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Message, InputMediaPhoto  # NEW: добавлен InputMediaPhoto (на всякий случай, если нужно)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

# Logging
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
log = logging.getLogger("DivineVPN-TicketBot")

# Load config
with open("config.json", "r", encoding="utf-8") as f:
    CFG = json.load(f)
TOKEN = CFG["TELEGRAM_TOKEN"]
CHANNEL_ID = int(CFG["CHANNEL_ID"])
BRAND = CFG.get("BRAND", "Atlanta VPN")
AUTO_CLOSE_HOURS = int(CFG.get("AUTO_CLOSE_HOURS", 3))
REMINDER_MINUTES = int(CFG.get("REMINDER_MINUTES", 15))
STATE_FILE = CFG.get("STATE_FILE", "state.json")

# Persistence helpers
def load_state() -> Dict[str, Any]:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.error("Failed to load state: %s", e)
    return {"tickets": {}, "stats": {}}

def save_state(state: Dict[str, Any]):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        log.error("Failed to save state: %s", e)

STATE = load_state()
TICKETS: Dict[str, Dict[str, Any]] = STATE.get("tickets", {})
STATS: Dict[str, Any] = STATE.get("stats", {})

# ---------------------------------FAQ structure---------------------------------------
CONTENT = {
    "🌐 Обходы": {
        "Куда пропали Моб.операторы?": "Теперь они называются Нидерланды 2 и Россия 2. Если они не работают, попробуйте использовать другие обходы - https://t.me/AtlantaVPNvideo/9",
        "Не работают «Белые списки»?": "Попробуйте, пожалуйста, обновить конфигурацию, заново добавить ключ в приложение или переустановить Happ.\n Попробуйте обязательно все обходы, которые доступны в подписке.\nОбходы работают только при белых списках, а не полном глушении интернета. \nУбедитесь, что используете именно обходы, а не основную подписку.\n Если все равно ни один обход не работает, то следите за обновлениями в нашем канале и в боте. Мы постоянно находимся в поиске новых обходов, обязательно найдется тот, который подойдет именно Вам!",
        "Пропали обходы": "Чтобы продолжить использование обхода, нужно пополнить гигабайты. Чтобы купить доп. гигабайты нужно в боте зайти в Мой профиль - Мои ключи - выбрать ваш ключ - Белые списки и нажать Купить гигабайты, далее следуете указаниям бота",
        "Можно купить обходы отдельно?": "Обходы — это доп. подписка к основной. Отдельно их купить нельзя.",
        "Как купить гигабайты? ": "Чтобы купить доп. гигабайты нужно в боте зайти в Мой профиль - Мои ключи - выбрать ваш ключ - Белые списки и нажать Купить гигабайты, далее следуете указаниям бота. Видеоинструкция - https://t.me/AtlantaVPNvideo/10",
        "Как купить гигабайты на пробный ключ? ": "Гигабайты для обхода можно купить только для оплаченной основной подписки.",
    },
    "🛜 VPN": {
        "Как подключить VPN?": "Инструкции для всех устройств можете найти в посте - https://t.me/AtlantaVPN/31, либо в видео инструкции - https://t.me/AtlantaVPNvideo/10",
        "Не работает VPN (Happ)": "Попробуйте обновить конфигурацию и выбрать другую страну подключения. Если не помогло, то переустановите Happ",
        "Не работает VPN (v2raytun)": "Попробуйте скачать приложение Happ и использовать его. Скачать можно по ссылке - https://www.happ.su/main/ru",
        "Низкая скорость при использовании VPN": "Попробуйте обновить конфигурацию и выбрать другую скорость подключения.",
        "Не работает TikTok (iOS)": "Попробуйте другую страну подключения и убедитесь, что регион в AppStore изменён (не Россия).",
    },
    "📢 Реферальная/партнерская программа": {
        "Не пришли деньги за реферала": "Убедитесь, что приглашаете людей по реферальной, а не партнерской ссылке. Если все верно, то реферал не до конца прошел регитсрацию. Для нее нужно подписаться на канал и выбрать язык в боте",
        "Куда можно выводить деньги по партнерской программе?": "Вывод средств осуществляется только на карты Российских банков",
    },
    "💳 Оплата": {
        "Как вернуть деньги за VPN?": "Мы возвращаем деньги, если не работает VPN, не предназначенный для обхода, и мы не можем Вам помочь. ",
        "Как отключить автоплатеж?": "Удалите метод оплаты в боте: Мой профиль -> Мой баланс -> Методы оплаты -> Удалить.",
    },
    "Другое": {
        "Сколько устройств можно подключить по одной подписке?": "Для каждого устройства нужна индивидуальная подписка",
        "Есть ли подписки для нескольких устройств?": "Такой подписки нет",
        "Ошибка TLS рукопожатия": "Попробуйте, пожалуйста, обновить конфигурацию и использовать другую страну подключения",
    },
}


def faq_categories_kb():
    buttons = [[InlineKeyboardButton(cat, callback_data=f"faq_cat:{cat}")] for cat in CONTENT.keys()]
    return InlineKeyboardMarkup(buttons)


def faq_questions_kb(category: str):
    if category not in CONTENT:
        category = "Другое"
    buttons = [[InlineKeyboardButton(q, callback_data=f"faq_q:{category}:{i}")]
               for i, q in enumerate(CONTENT[category].keys())]
    buttons.append([InlineKeyboardButton("❗ Нет моего вопроса", callback_data=f"faq_q:{category}:ticket")])
    buttons.append([InlineKeyboardButton("⬅️ Назад", callback_data="faq_back")])
    return InlineKeyboardMarkup(buttons)

def faq_answer_kb(category: str):
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=f"faq_cat:{category}")]])


#----------------------- Helpers----------------------------------
def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def mk_ticket_id(user_id: int) -> str:
    return f"{user_id}_{int(datetime.now(timezone.utc).timestamp())}"

PRIO_ICONS = {"high":"🔴","medium":"🟡","low":"🟢"}
CATEGORIES = {"Bypasses":"🌐 Обходы", "VPN":"🛜 VPN", "Payment":"💳 Оплата", "Program":"📢 Реферальная/партнерская программа", "Other":"Другое"}

# Keyboards (без изменений)
def client_priority_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔴 Срочно", callback_data="prio:high"),
        InlineKeyboardButton("🟡 Средне", callback_data="prio:medium"),
        InlineKeyboardButton("🟢 Не срочно", callback_data="prio:low")
    ]])

def client_category_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🌐 Обходы", callback_data="cat:Bypasses"),
        InlineKeyboardButton("🛜 VPN", callback_data="cat:VPN"),
        InlineKeyboardButton("💳 Оплата", callback_data="cat:Payment"),
        InlineKeyboardButton("📢 Реферальная/партнерская программа", callback_data="cat:Program"),
        InlineKeyboardButton("Другое", callback_data="cat:Other")
    ]])


def manager_thread_kb(ticket_id: str, taken_by: Optional[int]) -> InlineKeyboardMarkup:
    buttons = []
    if not taken_by:
        buttons.append(InlineKeyboardButton("✅ Взять тикет", callback_data=f"take:{ticket_id}"))
    else:
        buttons.append(InlineKeyboardButton("👤 Взял", callback_data="noop"))
    buttons.append(InlineKeyboardButton("🔄 Передать", callback_data=f"transfer:{ticket_id}"))
    buttons.append(InlineKeyboardButton("🔒 Закрыть", callback_data=f"close:{ticket_id}"))
    return InlineKeyboardMarkup([buttons])

def rating_kb(ticket_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("⭐️", callback_data=f"rate:{ticket_id}:1"),
        InlineKeyboardButton("⭐️⭐️", callback_data=f"rate:{ticket_id}:2"),
        InlineKeyboardButton("⭐️⭐️⭐️", callback_data=f"rate:{ticket_id}:3"),
        InlineKeyboardButton("⭐️⭐️⭐️⭐️", callback_data=f"rate:{ticket_id}:4"),
        InlineKeyboardButton("⭐️⭐️⭐️⭐️⭐️", callback_data=f"rate:{ticket_id}:5")
    ]])

async def ensure_reviews_thread(context: ContextTypes.DEFAULT_TYPE):
    reviews_id = STATE.get("reviews_thread_id")
    if not reviews_id:
        try:
            topic = await context.bot.create_forum_topic(chat_id=CHANNEL_ID, name="⭐ Отзывы")
            reviews_id = topic.message_thread_id
            STATE["reviews_thread_id"] = reviews_id
            save_state(STATE)
        except Exception as e:
            log.error("Failed to create reviews thread: %s", e)
            return None
    return reviews_id

# Flow: /start -> priority -> category -> create thread (без изменений)
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
    await update.message.reply_text(
        "👋 Здравствуйте! Выберите категорию вопроса:",
        reply_markup=faq_categories_kb()
    )

# client callback for priority/category (без изменений)
async def client_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data or ""
    if not context.user_data.get("creating_ticket"):
        await q.edit_message_text("❗ Начните /start чтобы создать тикет.")
        return
    ct = context.user_data["creating_ticket"]
    if data.startswith("prio:"):
        ct["priority"] = data.split(":",1)[1]
        await q.edit_message_text(f"Выбран приоритет: {PRIO_ICONS.get(ct['priority'])}\nВыберите категорию:", reply_markup=client_category_kb())
        return
    if data.startswith("cat:"):
        ct["category"] = data.split(":",1)[1]
        user_id = ct["user_id"]
        ticket_id = mk_ticket_id(user_id)
        ticket = {
            "ticket_id": ticket_id,
            "user_id": user_id,
            "username": ct.get("username"),
            "priority": ct.get("priority","low"),
            "category": ct.get("category","connect"),
            "created_at": now_utc().isoformat(),
            "last_client_msg_at": now_utc().isoformat(),
            "status": "open",
            "thread_id": None,
            "taken_by": None,
            "rating": None,
            "messages": []
        }
        TICKETS[ticket_id] = ticket
        STATE["tickets"] = TICKETS
        save_state(STATE)
        title = f"{PRIO_ICONS[ticket['priority']]} {CATEGORIES.get(ticket['category'])} — {ticket['username'] or ticket['user_id']}"
        try:
            topic = await context.bot.create_forum_topic(chat_id=CHANNEL_ID, name=title)
            thread_id = topic.message_thread_id
            ticket["thread_id"] = thread_id
            STATE["tickets"] = TICKETS
            save_state(STATE)
            text = (f"📩 Тикет {ticket_id}\n💻 ID клиента: {ticket['user_id']}\nКлиент: @{ticket['username'] or ticket['user_id']}\n"
                    f"Приоритет: {PRIO_ICONS[ticket['priority']]}\nКатегория: {CATEGORIES.get(ticket['category'])}\n\n"
                    "Менеджеры, нажмите «Взять тикет» чтобы подключиться.")
            await context.bot.send_message(chat_id=CHANNEL_ID, message_thread_id=thread_id, text=text, reply_markup=manager_thread_kb(ticket_id, None))
            # create logs thread if missing and log creation
            await ensure_logs_thread(context, f"Создан тикет {ticket_id} (пользователь {ticket['username'] or ticket['user_id']})")
        except Exception as e:
            log.error("create_forum_topic failed: %s", e)
            await q.edit_message_text("Ошибка при создании ветки форума: " + str(e))
            return
        await q.edit_message_text("✅ Тикет создан. Опишите проблему — постараемся оперативно помочь.")
        context.user_data.pop("creating_ticket", None)

# Ensure logs thread exists (named "📊 Логи") (без изменений)
async def ensure_logs_thread(context: ContextTypes.DEFAULT_TYPE, text: str):
    logs_id = STATE.get("logs_thread_id")
    if not logs_id:
        try:
            topic = await context.bot.create_forum_topic(chat_id=CHANNEL_ID, name="📊 Логи")
            STATE["logs_thread_id"] = topic.message_thread_id
            save_state(STATE)
            logs_id = topic.message_thread_id
        except Exception as e:
            log.error("Failed to create logs thread: %s", e)
            logs_id = None
    if logs_id:
        try:
            await context.bot.send_message(chat_id=CHANNEL_ID, message_thread_id=logs_id, text=text)
        except Exception as e:
            log.error("Failed to send log message: %s", e)

# MODIFIED: client dms -> forward to thread and update last_client_msg_at (теперь с поддержкой фото)
async def client_dm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
    user = update.effective_user
    msg: Message = update.message
    # --- обработка текстового отзыва после оценки ---
    if context.user_data.get("await_review"):
        ticket_id = context.user_data["await_review"]
        reviews_thread = await ensure_reviews_thread(context)

        try:
            await context.bot.send_message(
                chat_id=CHANNEL_ID,
                message_thread_id=reviews_thread,
                text=f"⭐ Отзыв по тикету {ticket_id} от @{user.username or user.id}:\n\n{msg.text}"
            )
        except Exception as e:
            log.error("Failed to post review: %s", e)

        context.user_data.pop("await_review", None)

        await msg.reply_text("Спасибо! Ваш отзыв отправлен 💙")
        return

    # find ticket
    ticket = None
    for t in TICKETS.values():
        if t["user_id"] == user.id and t["status"] in ("open","in_progress"):
            ticket = t
            break
    if not ticket:
        await msg.reply_text("У вас нет активного тикета. Нажмите /start чтобы создать.")
        return
    ticket["last_client_msg_at"] = now_utc().isoformat()

    # NEW: обработка фото или текста
    if msg.photo:  # NEW: если фото
        photo = msg.photo[-1]  # берём наилучшее качество
        file_id = photo.file_id
        caption = msg.caption or ""  # подпись к фото
        ticket["messages"].append({"from": "client", "type": "photo", "file_id": file_id, "caption": caption, "at": now_utc().isoformat()})
        log_text = f"фото (подпись: '{caption}') " if caption else "фото "
        try:
            await context.bot.send_photo(chat_id=CHANNEL_ID, message_thread_id=ticket["thread_id"], photo=file_id, caption=f"👤 Клиент: {caption}" if caption else "👤 Клиент:")
        except Exception as e:
            log.error("Failed to post client photo to thread: %s", e)
    else:  # текст (оригинальный код)
        ticket["messages"].append({"from": "client", "type": "text", "text": msg.text, "at": now_utc().isoformat()})
        log_text = f"сообщение: '{msg.text}' "
        try:
            await context.bot.send_message(chat_id=CHANNEL_ID, message_thread_id=ticket["thread_id"], text=f"👤 Клиент: {msg.text}")
        except Exception as e:
            log.error("Failed to post client msg to thread: %s", e)

    save_state(STATE)
    await ensure_logs_thread(context, f"Сообщение от клиента {ticket['user_id']}: {log_text}")

# manager callbacks (take, close, transfer) (без изменений)
async def manager_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data or ""
    if ":" not in data:
        return
    action, ticket_id = data.split(":",1)
    ticket = TICKETS.get(ticket_id)
    if not ticket:
        await q.edit_message_text("Тикет не найден.")
        return
    user_id = ticket["user_id"]
    if action == "take":
        if ticket["taken_by"]:
            await q.edit_message_text("Тикет уже взят.")
            return
        ticket["taken_by"] = q.from_user.id
        ticket["status"] = "in_progress"
        save_state(STATE)
        await q.edit_message_text(f"✅ Тикет {ticket_id} взят {q.from_user.first_name}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔒 Закрыть", callback_data=f"close:{ticket_id}"), InlineKeyboardButton("🔄 Передать", callback_data=f"transfer:{ticket_id}")]]))
        try:
            await context.bot.send_message(chat_id=user_id, text=f"✅ Менеджер подключился к вашему тикету.")
        except Exception as e:
            log.warning("Notify client on take failed: %s", e)
        await ensure_logs_thread(context, f"Взят тикет {ticket_id} менеджером {q.from_user.first_name}")
    elif action == "close":
        await do_close_ticket(context, ticket_id, reason=f"Закрыт менеджером {q.from_user.first_name}")
        await ensure_logs_thread(context, f"Закрыт тикет {ticket_id} менеджером {q.from_user.first_name}")
    elif action == "transfer":
        ticket["taken_by"] = None
        ticket["status"] = "open"
        save_state(STATE)
        await q.edit_message_text(f"🔄 Тикет {ticket_id} помечен как свободный.", reply_markup=manager_thread_kb(ticket_id, None))
        await ensure_logs_thread(context, f"Тикет {ticket_id} передан менеджером {q.from_user.first_name}")

# MODIFIED: manager messages inside thread -> forward to client (теперь с поддержкой фото)
async def manager_thread_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg: Message = update.message
    if not msg or msg.message_thread_id is None:
        return
    thread_id = msg.message_thread_id
    ticket = None
    for t in TICKETS.values():
        if t.get("thread_id") == thread_id:
            ticket = t
            break
    if not ticket or ticket.get("status") == "closed":
        return
    # forward manager message to client
    if msg.photo:  # NEW: если фото
        photo = msg.photo[-1]
        file_id = photo.file_id
        caption = msg.caption or ""
        ticket["messages"].append({"from": "manager", "type": "photo", "file_id": file_id, "caption": caption, "at": now_utc().isoformat()})
        log_text = f"фото (подпись: '{caption}') " if caption else "фото "
        try:
            await context.bot.send_photo(chat_id=ticket["user_id"], photo=file_id, caption=f"💬 Менеджер: {caption}" if caption else "💬 Менеджер:")
        except Exception as e:
            log.error("Failed to forward manager photo: %s", e)
    else:  # текст (оригинальный код)
        ticket["messages"].append({"from": "manager", "type": "text", "text": msg.text, "at": now_utc().isoformat()})
        log_text = f"сообщение: '{msg.text}' "
        try:
            await context.bot.send_message(chat_id=ticket["user_id"], text=f"💬 Менеджер: {msg.text}")
        except Exception as e:
            log.error("Failed to forward manager msg: %s", e)

    save_state(STATE)
    # NEW: лог для менеджера (опционально, можно убрать если не нужно)
    await ensure_logs_thread(context, f"Сообщение от менеджера в тикет {ticket['ticket_id']}: {log_text}")

async def faq_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data or ""

    # Назад из вопросов в категории
    if data == "faq_back":
        await q.edit_message_text(
            "👆 Выберите категорию вопроса:",
            reply_markup=faq_categories_kb()
        )
        return

    # Выбор категории
    if data.startswith("faq_cat:"):
        category = data.split(":",1)[1]
        await q.edit_message_text(
            f"❓ Вопросы в категории {category}:",
            reply_markup=faq_questions_kb(category)
        )
        return

    # Выбор конкретного вопроса
    if data.startswith("faq_q:"):
        _, category, idx = data.split(":")
        if idx == "ticket":
            # Запускаем создание тикета
            context.user_data["creating_ticket"] = {
                "user_id": q.from_user.id,
                "username": q.from_user.username or q.from_user.first_name
            }
            await q.edit_message_text(
                "❗ Вы не нашли ответ? Создадим тикет для оператора. Выберите срочность:",
                reply_markup=client_priority_kb()
            )
            return

        # idx — число, берем вопрос из CONTENT
        idx = int(idx)
        category_dict = CONTENT.get(category, CONTENT["Другое"])
        questions_list = list(category_dict.items())
        question, answer = questions_list[idx]

        await q.edit_message_text(
            f"❓ {question}\n\n💡 {answer}",
            reply_markup=faq_answer_kb(category)
        )

# rating handler (без изменений)
async def rating_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split(":")
    if len(parts) != 3:
        return
    _, ticket_id, score = parts
    t = TICKETS.get(ticket_id)
    if not t:
        return

    t["rating"] = int(score)
    save_state(STATE)

    # благодарность
    await q.edit_message_text(f"Спасибо! Вы оценили поддержку на {score} ⭐️")
    # включаем режим ожидания отзыва
    context.user_data["await_review"] = ticket_id
    # просим оставить текст
    await q.message.reply_text("✍️ Пожалуйста, напишите текстовый отзыв о работе поддержки.")

    await ensure_logs_thread(context, f"Оценка тикета {ticket_id}: {score}")

# close ticket helper (без изменений)
async def do_close_ticket(context: ContextTypes.DEFAULT_TYPE, ticket_id: str, reason: str):
    t = TICKETS.get(ticket_id)
    if not t or t.get("status") == "closed":
        return
    t["status"] = "closed"
    save_state(STATE)
    # notify thread & client
    try:
        if t.get("thread_id"):
            await context.bot.send_message(chat_id=CHANNEL_ID, message_thread_id=t["thread_id"], text=f"🔒 Тикет закрыт: {reason}")
    except Exception as e:
        log.error("Failed to notify thread: %s", e)
    try:
        await context.bot.send_message(chat_id=t["user_id"], text=f"✅ Ваш тикет закрыт. {reason}", reply_markup=rating_kb(ticket_id))
    except Exception as e:
        log.error("Failed to notify client: %s", e)
    # delete forum topic
    if t.get("thread_id"):
        try:
            await context.bot.delete_forum_topic(chat_id=CHANNEL_ID, message_thread_id=t["thread_id"])
        except Exception as e:
            log.error("Failed to delete forum topic: %s", e)
    await ensure_logs_thread(context, f"Закрыт тикет {ticket_id}: {reason}")

# periodic job: reminder and auto-close (без изменений)
async def job_checker(context: ContextTypes.DEFAULT_TYPE):
    now = now_utc()
    for ticket_id, t in list(TICKETS.items()):
        if t.get("status") not in ("open","in_progress"):
            continue
        last = datetime.fromisoformat(t.get("last_client_msg_at"))
        elapsed = now - last
        hours = elapsed.total_seconds() / 3600.0
        # reminder
        if hours >= (AUTO_CLOSE_HOURS - REMINDER_MINUTES/60.0) and not t.get("reminder_sent"):
            try:
                await context.bot.send_message(chat_id=t["user_id"], text=f"⏳ Через {REMINDER_MINUTES} минут тикет будет автоматически закрыт из-за неактивности. Если нужно продолжить — отправьте сообщение.")
                t["reminder_sent"] = True
                save_state(STATE)
                await ensure_logs_thread(context, f"Напоминание тикету {ticket_id} отправлено")
            except Exception as e:
                log.error("Failed to send reminder: %s", e)
        # auto-close
        if hours >= AUTO_CLOSE_HOURS:
            await do_close_ticket(context, ticket_id, reason="Авто-закрытие: нет активности 3 часа")

# simple stats (private command) (без изменений)
async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
    total = len(TICKETS)
    open_cnt = sum(1 for t in TICKETS.values() if t.get("status") in ("open","in_progress"))
    closed = sum(1 for t in TICKETS.values() if t.get("status")=="closed")
    avg_rating = None
    ratings = [t.get("rating") for t in TICKETS.values() if isinstance(t.get("rating"), int)]
    if ratings:
        avg_rating = sum(ratings)/len(ratings)
    text = f"📊 Статистика (в памяти):\nВсего тикетов: {total}\nОткрытых: {open_cnt}\nЗакрытых: {closed}\nСредний рейтинг: {avg_rating or '—'}"
    await update.message.reply_text(text)

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(faq_cb, pattern=r"^faq_"))
    app.add_handler(CallbackQueryHandler(client_cb, pattern=r"^(prio|cat):"))

    # MODIFIED: разделил обработчики для текста и фото в привате
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND & ~filters.PHOTO, client_dm))  # MODIFIED: добавил ~filters.PHOTO
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.PHOTO, client_dm))  # NEW: отдельный для фото (но функция client_dm теперь универсальная)
    app.add_handler(CallbackQueryHandler(manager_cb, pattern=r"^(take|close|transfer):"))
    # MODIFIED: разделил обработчики для текста и фото в канале
    app.add_handler(MessageHandler(filters.Chat(CHANNEL_ID) & filters.TEXT & ~filters.COMMAND & ~filters.PHOTO, manager_thread_msg))  # MODIFIED: добавил ~filters.PHOTO
    app.add_handler(MessageHandler(filters.Chat(CHANNEL_ID) & filters.PHOTO & ~filters.COMMAND, manager_thread_msg))  # NEW: отдельный для фото
    app.add_handler(CallbackQueryHandler(rating_cb, pattern=r"^rate:"))
    app.add_handler(CommandHandler("stats", stats_cmd))

    # job queue for reminders and auto-close
    app.job_queue.run_repeating(job_checker, interval=60, first=30)

    log.info(f"🚀 {BRAND} Ticket Bot PRO started. Channel {CHANNEL_ID}")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()