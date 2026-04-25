import os
import logging
from groq import Groq
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
 
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
 
GROQ_API_KEY   = os.environ.get("GROQ_API_KEY", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
 
client = Groq(api_key=GROQ_API_KEY)
 
SYSTEM_PROMPT = """Ты — дружелюбный и терпеливый преподаватель английского языка для русскоязычных студентов. Студент — абсолютный новичок (уровень A0/A1), изучает английский с нуля.
 
ТВОЙ СТИЛЬ:
- Общаешься преимущественно на РУССКОМ языке
- Постепенно вводишь английские слова и фразы с переводом в скобках
- Объясняешь просто, с примерами и юмором
- Всегда хвалишь за правильные ответы, мягко исправляешь ошибки
- Используешь эмодзи для живости
 
СТРУКТУРА УРОКА при запросе темы:
1. Приветствие и вводное слово о теме
2. 5-7 новых слов/фраз с произношением [в квадратных скобках]
3. Примеры в простых предложениях
4. Небольшое упражнение прямо в чате (2-3 вопроса/задания)
5. В конце ОБЯЗАТЕЛЬНО давай домашнее задание в таком формате:
 
📚 ДОМАШНЕЕ ЗАДАНИЕ:
1. [задание первое]
2. [задание второе]
3. [задание третье]
 
ПРОВЕРКА ДОМАШНЕГО ЗАДАНИЯ:
- Проверяй каждый ответ подробно
- Объясняй ошибки с правильным вариантом
- Ставь итоговую оценку: "Результат: X/3 ⭐"
 
Отвечай развёрнуто, но не слишком длинно. Максимум 400 слов."""
 
TOPICS = {
    "greetings": "👋 Приветствия и знакомство",
    "numbers":   "🔢 Числа и счёт",
    "colors":    "🎨 Цвета и описание",
    "family":    "👨‍👩‍👧 Семья и люди",
    "food":      "🍎 Еда и напитки",
    "time":      "⏰ Время и дни недели",
    "tobe":      "📝 Грамматика: глагол To Be",
    "pronouns":  "📝 Грамматика: Местоимения",
    "present":   "📝 Грамматика: Present Simple",
    "articles":  "📝 Грамматика: Артикли a/an/the",
}
 
user_data: dict = {}
 
def get_user(user_id: int) -> dict:
    if user_id not in user_data:
        user_data[user_id] = {
            "history": [],
            "homework": [],
            "done_topics": [],
            "current_topic": None,
        }
    return user_data[user_id]
 
def topics_keyboard() -> InlineKeyboardMarkup:
    rows = []
    items = list(TOPICS.items())
    for i in range(0, len(items), 2):
        row = []
        for key, label in items[i:i+2]:
            row.append(InlineKeyboardButton(label, callback_data=f"topic:{key}"))
        rows.append(row)
    rows.append([InlineKeyboardButton("📋 Моё домашнее задание", callback_data="show_hw")])
    return InlineKeyboardMarkup(rows)
 
def extract_homework(text: str, uid: int):
    marker = "📚 ДОМАШНЕЕ ЗАДАНИЕ:"
    if marker not in text:
        return
    after = text.split(marker, 1)[1]
    lines = after.strip().split("\n")
    tasks = []
    for line in lines:
        line = line.strip()
        if line and line[0].isdigit() and "." in line:
            task = line.split(".", 1)[1].strip()
            if task:
                tasks.append(task)
    ud = get_user(uid)
    for t in tasks:
        if not any(h["text"] == t for h in ud["homework"]):
            ud["homework"].append({"text": t, "done": False})
 
def ask_groq(uid: int, user_msg: str) -> str:
    ud = get_user(uid)
    ud["history"].append({"role": "user", "content": user_msg})
    history = ud["history"][-14:]
 
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history
 
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=800,
        messages=messages,
    )
    reply = resp.choices[0].message.content
    ud["history"].append({"role": "assistant", "content": reply})
    if len(ud["history"]) > 40:
        ud["history"] = ud["history"][-30:]
    extract_homework(reply, uid)
    return reply
 
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    get_user(uid)
    name = update.effective_user.first_name or "друг"
    await update.message.reply_text(
        f"👋 Привет, {name}!\n\n"
        "Я твой персональный преподаватель английского языка 🇬🇧\n\n"
        "Мы начнём с самого нуля и дойдём до уровня, где ты сможешь свободно общаться на английском!\n\n"
        "📌 Выбери тему для первого урока:",
        reply_markup=topics_keyboard()
    )
 
async def cmd_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📚 Выбери тему урока:",
        reply_markup=topics_keyboard()
    )
 
async def cmd_hw(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ud = get_user(uid)
    hw = ud["homework"]
    if not hw:
        await update.message.reply_text(
            "У тебя пока нет домашних заданий.\nПройди урок — и они появятся! 📖",
            reply_markup=topics_keyboard()
        )
        return
    text = "📋 <b>Твои домашние задания:</b>\n\n"
    for i, h in enumerate(hw, 1):
        status = "✅" if h["done"] else "⬜"
        text += f"{status} {i}. {h['text']}\n"
    text += "\n💡 Напиши свои ответы в чат — я проверю!"
    await update.message.reply_text(text, parse_mode="HTML")
 
async def cmd_reset(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_data[uid] = {
        "history": [],
        "homework": [],
        "done_topics": [],
        "current_topic": None,
    }
    await update.message.reply_text(
        "🔄 Всё сброшено! Начинаем заново.\n\nВыбери тему:",
        reply_markup=topics_keyboard()
    )
 
async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = query.data
 
    if data == "show_hw":
        ud = get_user(uid)
        hw = ud["homework"]
        if not hw:
            await query.message.reply_text(
                "У тебя пока нет домашних заданий.\nПройди урок — и они появятся! 📖"
            )
        else:
            text = "📋 <b>Твои домашние задания:</b>\n\n"
            for i, h in enumerate(hw, 1):
                status = "✅" if h["done"] else "⬜"
                text += f"{status} {i}. {h['text']}\n"
            text += "\n💡 Напиши свои ответы в чат — я проверю!"
            await query.message.reply_text(text, parse_mode="HTML")
        return
 
    if data.startswith("topic:"):
        key = data.split(":", 1)[1]
        label = TOPICS.get(key, key)
        ud = get_user(uid)
        ud["current_topic"] = label
 
        await query.message.reply_text(
            f"📖 Начинаем урок: <b>{label}</b>\n\n⏳ Готовлю урок...",
            parse_mode="HTML"
        )
        prompt = f"[ТЕМА УРОКА: {label}]\nНачни урок по этой теме. Дай полный урок: объяснение, новые слова, примеры, упражнение и домашнее задание."
        reply = ask_groq(uid, prompt)
        await query.message.reply_text(reply)
 
async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()
    if not text:
        return
 
    await ctx.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    reply = ask_groq(uid, text)
 
    ud = get_user(uid)
    lower = text.lower()
    if any(word in lower for word in ["проверь", "мой ответ", "задание", "домашн"]):
        for h in ud["homework"]:
            if not h["done"] and h["text"].lower() in text.lower():
                h["done"] = True
 
    for chunk in [reply[i:i+4000] for i in range(0, len(reply), 4000)]:
        await update.message.reply_text(chunk)
 
def main():
    if not TELEGRAM_TOKEN:
        raise ValueError("Не задан TELEGRAM_TOKEN!")
    if not GROQ_API_KEY:
        raise ValueError("Не задан GROQ_API_KEY!")
 
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("menu",   cmd_menu))
    app.add_handler(CommandHandler("hw",     cmd_hw))
    app.add_handler(CommandHandler("reset",  cmd_reset))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
 
    logger.info("Бот запущен!")
    app.run_polling(drop_pending_updates=True)
 
if __name__ == "__main__":
    main()
 
