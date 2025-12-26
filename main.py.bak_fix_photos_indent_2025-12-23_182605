#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MGIMO Dating Bot - DiplomatMatch

Функции:
- Создание анкеты с фото, именем, возрастом, факультетом
- Редактирование анкеты
- Деление по полу: парни / девушки
- Месячная подписка для парней (через YooKassa)
- Хранение срока окончания подписки и флага автопродления
- Просмотр анкет противоположного пола
- Лайки, дизлайки, мэтчи (обмен Telegram-никами)
- Включение / выключение своей анкеты (is_active)
"""

import logging
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InputMediaPhoto,
    User as TgUser,
)
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ----- YooKassa -----
from yookassa import Configuration, Payment

# ===== НАСТРОЙКИ БОТА / ЮКАССЫ =====

BOT_TOKEN = "8178878634:AAE30ItG3Kqt1HlUL0DdOPpSPZUatTO9nM0"  # сюда токен твоего бота
DB_PATH = "mgimo_dating_bot.db"

# username бота в Telegram БЕЗ @
BOT_USERNAME = "diplomatch_bot"  # например "Diplomatch_bot"

SUBSCRIPTION_PRICE_RUB = "1490.00"
SUBSCRIPTION_DESCRIPTION = "DiplomatMatch subscription"

# YooKassa credentials (shop_id + secret_key)
Configuration.account_id = "1198180"
Configuration.secret_key = "live_WPuu5SnDi7JqFPcrr8wIIeL-eQ7264E-WxmhSR8Q6jc"

# Ссылка, куда ЮKassa вернёт пользователя после оплаты
RETURN_URL = f"https://t.me/{BOT_USERNAME}"

# ===== ЛОГИ =====

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ===== КОНСТАНТЫ =====

GENDER_MALE = "male"
GENDER_FEMALE = "female"

PROFILE_STEP_PHOTO = "photo"
PROFILE_STEP_NAME = "name"
PROFILE_STEP_AGE = "age"
PROFILE_STEP_FACULTY = "faculty"
PROFILE_STEP_CONFIRM = "confirm"

PROFILE_PHOTOS_DONE = "profile_photos_done"

UD_PROFILE_WIZARD = "profile_wizard"

# ---------------------------------------------------------------------------
# БАЗА ДАННЫХ
# ---------------------------------------------------------------------------


class Database:
    def __init__(self, path: str) -> None:
        self.path = path
        self._ensure_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_db(self) -> None:
        """
        Инициализация БД.
        Для старых баз можно было делать миграцию, но сейчас мы исходим из
        новой схемы (users уже содержит subscription_until и auto_renew).
        """
        conn = self._connect()
        c = conn.cursor()

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id            INTEGER PRIMARY KEY,
                username           TEXT,
                first_name         TEXT,
                last_name          TEXT,
                gender             TEXT,
                is_premium         INTEGER DEFAULT 0,
                subscription_until TEXT,
                auto_renew         INTEGER DEFAULT 1,
                created_at         TEXT,
                updated_at         TEXT
            )
            """
        )

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS profiles (
                user_id         INTEGER PRIMARY KEY,
                photo_file_id   TEXT,
                photo_file_id2  TEXT,
                photo_file_id3  TEXT,
                name            TEXT,
                age             INTEGER,
                faculty         TEXT,
                is_active       INTEGER DEFAULT 1,
                created_at      TEXT,
                updated_at      TEXT,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
            """
        )

        for extra_photo_col in ("photo_file_id2", "photo_file_id3"):
            if not self._column_exists(conn, "profiles", extra_photo_col):
                c.execute(
                    f"ALTER TABLE profiles ADD COLUMN {extra_photo_col} TEXT"
                )

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS likes (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user_id    INTEGER NOT NULL,
                to_user_id      INTEGER NOT NULL,
                is_like         INTEGER NOT NULL,
                created_at      TEXT,
                UNIQUE(from_user_id, to_user_id),
                FOREIGN KEY(from_user_id) REFERENCES users(user_id),
                FOREIGN KEY(to_user_id) REFERENCES users(user_id)
            )
            """
        )

        conn.commit()
        conn.close()

    def _column_exists(self, conn: sqlite3.Connection, table: str, column: str) -> bool:
        cur = conn.execute(f"PRAGMA table_info({table})")
        for row in cur.fetchall():
            if row[1] == column:
                return True
        return False

    def _now(self) -> str:
        return datetime.utcnow().isoformat()

    # ----- users -----

    def get_user(self, user_id: int) -> Optional[sqlite3.Row]:
        conn = self._connect()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        conn.close()
        return row

    def ensure_user(self, tg_user: TgUser, gender: Optional[str] = None) -> sqlite3.Row:
        row = self.get_user(tg_user.id)
        now = self._now()
        conn = self._connect()
        c = conn.cursor()

        if row is None:
            c.execute(
                """
                INSERT INTO users (user_id, username, first_name, last_name, gender,
                                   is_premium, subscription_until, auto_renew,
                                   created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tg_user.id,
                    tg_user.username,
                    tg_user.first_name,
                    tg_user.last_name,
                    gender,
                    0,
                    None,
                    1,
                    now,
                    now,
                ),
            )
        else:
            c.execute(
                """
                UPDATE users
                SET username = ?, first_name = ?, last_name = ?,
                    gender = COALESCE(?, gender),
                    updated_at = ?
                WHERE user_id = ?
                """,
                (
                    tg_user.username,
                    tg_user.first_name,
                    tg_user.last_name,
                    gender,
                    now,
                    tg_user.id,
                ),
            )

        conn.commit()
        c.execute("SELECT * FROM users WHERE user_id = ?", (tg_user.id,))
        updated = c.fetchone()
        conn.close()
        return updated

    def set_user_gender(self, user_id: int, gender: str) -> None:
        conn = self._connect()
        c = conn.cursor()
        c.execute(
            "UPDATE users SET gender = ?, updated_at = ? WHERE user_id = ?",
            (gender, self._now(), user_id),
        )
        conn.commit()
        conn.close()

    def update_subscription(
        self,
        user_id: int,
        is_premium: bool,
        until: Optional[datetime],
        auto_renew: Optional[bool] = None,
    ) -> None:
        """
        Обновление статуса подписки:
        - is_premium: активна / нет
        - until: datetime окончания периода или None
        - auto_renew: флаг автопродления (если None — не трогаем)
        """
        conn = self._connect()
        c = conn.cursor()
        now = self._now()
        until_str = until.isoformat() if until else None

        if auto_renew is None:
            c.execute(
                """
                UPDATE users
                SET is_premium = ?, subscription_until = ?, updated_at = ?
                WHERE user_id = ?
                """,
                (1 if is_premium else 0, until_str, now, user_id),
            )
        else:
            c.execute(
                """
                UPDATE users
                SET is_premium = ?, subscription_until = ?, auto_renew = ?, updated_at = ?
                WHERE user_id = ?
                """,
                (1 if is_premium else 0, until_str, 1 if auto_renew else 0, now, user_id),
            )

        conn.commit()
        conn.close()

    def set_auto_renew(self, user_id: int, value: bool) -> None:
        conn = self._connect()
        c = conn.cursor()
        c.execute(
            """
            UPDATE users
            SET auto_renew = ?, updated_at = ?
            WHERE user_id = ?
            """,
            (1 if value else 0, self._now(), user_id),
        )
        conn.commit()
        conn.close()

    def get_premium_info(
        self, user_id: int
    ) -> Tuple[bool, Optional[datetime], bool]:
        """
        Возвращает:
        - is_premium (с учётом возможного истечения срока)
        - subscription_until (datetime или None)
        - auto_renew (bool)
        Если срок истёк — обновляем запись в БД (is_premium = 0).
        """
        row = self.get_user(user_id)
        if not row:
            return False, None, False

        is_premium = bool(row["is_premium"])
        sub_until_str = row["subscription_until"]
        auto_renew = bool(row["auto_renew"]) if row["auto_renew"] is not None else False

        sub_until: Optional[datetime] = None
        if sub_until_str:
            try:
                sub_until = datetime.fromisoformat(sub_until_str)
            except Exception:
                sub_until = None

        # Если подписка активна, но срок истёк — деактивируем
        if is_premium and sub_until and datetime.utcnow() > sub_until:
            self.update_subscription(user_id, False, None, False)
            return False, sub_until, False

        return is_premium, sub_until, auto_renew

    # ----- profiles -----

    def get_profile(self, user_id: int) -> Optional[sqlite3.Row]:
        conn = self._connect()
        c = conn.cursor()
        c.execute("SELECT * FROM profiles WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        conn.close()
        return row

    def upsert_profile(
        self,
        user_id: int,
        photo_file_ids: List[str],
        name: str,
        age: int,
        faculty: str,
        is_active: bool = True,
    ) -> sqlite3.Row:
        now = self._now()
        conn = self._connect()
        c = conn.cursor()
        existing = self.get_profile(user_id)

        photos = (photo_file_ids + [None, None, None])[:3]

        if existing is None:
            c.execute(
                """
                INSERT INTO profiles (user_id, photo_file_id, photo_file_id2, photo_file_id3,
                                      name, age, faculty, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    photos[0],
                    photos[1],
                    photos[2],
                    name,
                    age,
                    faculty,
                    1 if is_active else 0,
                    now,
                    now,
                ),
            )
        else:
            c.execute(
                """
                UPDATE profiles
                SET photo_file_id = ?, photo_file_id2 = ?, photo_file_id3 = ?,
                    name = ?, age = ?, faculty = ?, is_active = ?, updated_at = ?
                WHERE user_id = ?
                """,
                (
                    photos[0],
                    photos[1],
                    photos[2],
                    name,
                    age,
                    faculty,
                    1 if is_active else 0,
                    now,
                    user_id,
                ),
            )

        conn.commit()
        c.execute("SELECT * FROM profiles WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        conn.close()
        return row

    def set_profile_active(self, user_id: int, is_active: bool) -> None:
        conn = self._connect()
        c = conn.cursor()
        c.execute(
            "UPDATE profiles SET is_active = ?, updated_at = ? WHERE user_id = ?",
            (1 if is_active else 0, self._now(), user_id),
        )
        conn.commit()
        conn.close()

    def has_complete_profile(self, user_id: int) -> bool:
        """
        Проверяем только заполненность полей, НЕ учитывая is_active.
        """
        p = self.get_profile(user_id)
        if p is None:
            return False
        if not profile_photo_ids(p):
            return False
        for f in ("name", "age", "faculty"):
            if p[f] is None:
                return False
        return True

    # ----- likes -----

    def set_like(self, from_user_id: int, to_user_id: int, is_like: bool) -> None:
        conn = self._connect()
        c = conn.cursor()
        now = self._now()
        c.execute(
            """
            INSERT INTO likes (from_user_id, to_user_id, is_like, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(from_user_id, to_user_id)
            DO UPDATE SET is_like = excluded.is_like,
                          created_at = excluded.created_at
            """,
            (from_user_id, to_user_id, 1 if is_like else 0, now),
        )
        conn.commit()
        conn.close()

    def has_mutual_like(self, user_a: int, user_b: int) -> bool:
        conn = self._connect()
        c = conn.cursor()
        c.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM likes
            WHERE ((from_user_id = ? AND to_user_id = ?) OR
                   (from_user_id = ? AND to_user_id = ?))
              AND is_like = 1
            """,
            (user_a, user_b, user_b, user_a),
        )
        row = c.fetchone()
        conn.close()
        return row["cnt"] == 2

    def get_next_candidate_for(
        self, viewer_id: int, viewer_gender: Optional[str]
    ) -> Optional[sqlite3.Row]:
        """
        Возвращает случайную подходящую анкету.
        """
        conn = self._connect()
        c = conn.cursor()

        if viewer_gender in (GENDER_MALE, GENDER_FEMALE):
            other_gender = (
                GENDER_FEMALE if viewer_gender == GENDER_MALE else GENDER_MALE
            )
            gender_condition = "AND u.gender = ?"
            params = [viewer_id, other_gender, viewer_id]
        else:
            gender_condition = ""
            params = [viewer_id, viewer_id]

        query = f"""
            SELECT p.*, u.username, u.gender
            FROM profiles p
            JOIN users u ON u.user_id = p.user_id
            WHERE p.user_id != ?
              AND p.is_active = 1
              AND (
                    p.photo_file_id IS NOT NULL
                 OR p.photo_file_id2 IS NOT NULL
                 OR p.photo_file_id3 IS NOT NULL
              )
              AND p.name IS NOT NULL
              AND p.age IS NOT NULL
              AND p.faculty IS NOT NULL
              {gender_condition}
              AND p.user_id NOT IN (
                    SELECT to_user_id
                    FROM likes
                    WHERE from_user_id = ?
              )
            ORDER BY RANDOM()
            LIMIT 1
        """
        c.execute(query, params)
        row = c.fetchone()
        conn.close()
        return row

    def get_username(self, user_id: int) -> Optional[str]:
        conn = self._connect()
        c = conn.cursor()
        c.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        conn.close()
        if row and row["username"]:
            return row["username"]
        return None


db = Database(DB_PATH)


def profile_photo_ids(profile: Optional[sqlite3.Row]) -> List[str]:
    if not profile:
        return []

    photos: List[str] = []
    for key in ("photo_file_id", "photo_file_id2", "photo_file_id3"):
        try:
            val = profile[key]
        except Exception:
            val = None
        if val:
            photos.append(val)
    return photos


async def send_photos_with_caption(
    bot,
    chat_id: int,
    photos: List[str],
    caption: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
):
    if photos and len(photos) > 1:
        media = [InputMediaPhoto(media=p) for p in photos]
        await bot.send_media_group(chat_id=chat_id, media=media)
        await bot.send_message(chat_id=chat_id, text=caption, reply_markup=reply_markup)
    elif photos:
        await bot.send_photo(
            chat_id=chat_id, photo=photos[0], caption=caption, reply_markup=reply_markup
        )
    else:
        await bot.send_message(chat_id=chat_id, text=caption, reply_markup=reply_markup)

# ---------------------------------------------------------------------------
# КЛАВИАТУРЫ
# ---------------------------------------------------------------------------


def main_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("👤 Моя анкета", callback_data="view_profile")],
        [
            InlineKeyboardButton(
                "✏️ Создать / редактировать анкету", callback_data="edit_profile"
            )
        ],
        [InlineKeyboardButton("📖 Смотреть анкеты", callback_data="browse_profiles")],
        [InlineKeyboardButton("💎 Подписка", callback_data="subscription")],
        [InlineKeyboardButton("❓ Помощь", callback_data="help")],
    ]
    return InlineKeyboardMarkup(keyboard)


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("⬅️ В главное меню", callback_data="back_to_menu")]]
    )


def genders_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Я парень 👨", callback_data="gender_male"),
                InlineKeyboardButton("Я девушка 👩", callback_data="gender_female"),
            ]
        ]
    )


def profile_edit_keyboard(is_active: bool) -> InlineKeyboardMarkup:
    """
    Клавиатура под своей анкетой: редактирование + включить/выключить.
    """
    toggle_btn = (
        InlineKeyboardButton("🔴 Выключить анкету", callback_data="profile_deactivate")
        if is_active
        else InlineKeyboardButton("🟢 Включить анкету", callback_data="profile_activate")
    )

    keyboard = [
        [
            InlineKeyboardButton("📸 Переснять фото", callback_data="edit_profile_photo"),
        ],
        [InlineKeyboardButton("📝 Изменить имя", callback_data="edit_profile_name")],
        [InlineKeyboardButton("🎂 Изменить возраст", callback_data="edit_profile_age")],
        [
            InlineKeyboardButton(
                "🏫 Изменить факультет", callback_data="edit_profile_faculty"
            )
        ],
        [toggle_btn],
        [InlineKeyboardButton("✅ Завершить", callback_data="back_to_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def browse_profile_keyboard(target_user_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("👎 Дизлайк", callback_data=f"dislike_{target_user_id}"),
            InlineKeyboardButton("👍 Лайк", callback_data=f"like_{target_user_id}"),
        ],
        [InlineKeyboardButton("➡️ Следующая анкета", callback_data="next_profile")],
        [InlineKeyboardButton("⬅️ В главное меню", callback_data="back_to_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


# ---------------------------------------------------------------------------
# УТИЛИТА: безопасное редактирование сообщений (текст/фото)
# ---------------------------------------------------------------------------


async def safe_edit(
    q, text: str, kb: Optional[InlineKeyboardMarkup] = None, **kwargs
) -> None:
    """
    Пробуем редактировать текст, если не получилось — подпись,
    если и это не сработало — отправляем новое сообщение.
    """
    try:
        await q.edit_message_text(text=text, reply_markup=kb, **kwargs)
    except Exception:
        try:
            await q.edit_message_caption(caption=text, reply_markup=kb, **kwargs)
        except Exception:
            try:
                await q.message.reply_text(text=text, reply_markup=kb, **kwargs)
            except Exception as e:
                logger.warning("Failed to send message in safe_edit: %s", e)


# ---------------------------------------------------------------------------
# НАВИГАЦИЯ
# ---------------------------------------------------------------------------


async def send_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "Главное меню MGIMO Dating Bot 💘\n\n"
        "Выбирай действие в кнопках ниже."
    )

    if update.callback_query:
        q = update.callback_query
        await q.answer()

        if q.message and q.message.photo:
            try:
                await q.edit_message_caption(
                    caption=text,
                    reply_markup=main_menu_keyboard(),
                )
            except Exception:
                await q.message.reply_text(
                    text,
                    reply_markup=main_menu_keyboard(),
                )
        else:
            try:
                await q.edit_message_text(
                    text=text,
                    reply_markup=main_menu_keyboard(),
                )
            except Exception:
                await q.message.reply_text(
                    text,
                    reply_markup=main_menu_keyboard(),
                )
    else:
        assert update.message
        await update.message.reply_text(text, reply_markup=main_menu_keyboard())


# ---------------------------------------------------------------------------
# ПОЛ
# ---------------------------------------------------------------------------


async def handle_gender_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    tg_user = q.from_user

    if q.data == "gender_male":
        gender = GENDER_MALE
    else:
        gender = GENDER_FEMALE

    db.ensure_user(tg_user, gender=gender)

    text = (
        "Пол сохранён ✅\n\n"
        "Теперь можно пользоваться ботом. Открываю главное меню 👇"
    )

    await update.message.reply_text(
    text, main_menu_keyboard())


# ---------------------------------------------------------------------------
# ПРОФИЛЬ: ПРОСМОТР
# ---------------------------------------------------------------------------


async def send_profile_view(
    update: Update, context: ContextTypes.DEFAULT_TYPE, from_callback: bool = True
) -> None:
    tg_user = update.effective_user
    if not tg_user:
        return
    db.ensure_user(tg_user)
    profile = db.get_profile(tg_user.id)

    if profile and db.has_complete_profile(tg_user.id):
        status = (
            "активна и показывается другим"
            if profile["is_active"]
            else "выключена и не показывается другим"
        )
        photos = profile_photo_ids(profile)
        text_lines = [
            "Твоя анкета выглядит так:",
            "",
            f"Имя: {profile['name']}",
            f"Возраст: {profile['age']}",
            f"Факультет: {profile['faculty']}",
            f"Статус: {status}",
        ]
        text = "\n".join(text_lines)
        kb = profile_edit_keyboard(bool(profile["is_active"]))

        if from_callback and update.callback_query:
            q = update.callback_query
            await q.answer()
            await send_photos_with_caption(
                context.bot, q.from_user.id, photos, text, kb
            )
            await safe_edit(
                q,
                "Я отправил твою анкету выше 👆",
                back_to_menu_keyboard(),
            )
        else:
            assert update.message
            await send_photos_with_caption(
                context.bot, tg_user.id, photos, text, kb
            )
    else:
        msg = (
            "У тебя пока нет анкеты 😔\n\n"
            "Давай создадим первую анкету. Это займет 1–2 минуты."
        )
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🚀 Создать анкету", callback_data="start_profile_wizard"
                    )
                ],
                [InlineKeyboardButton("⬅️ В главное меню", callback_data="back_to_menu")],
            ]
        )
        if from_callback and update.callback_query:
            q = update.callback_query
            await q.answer()
            await safe_edit(q, msg, kb)
        else:
            assert update.message
            await update.message.reply_text(msg, reply_markup=kb)


# ---------------------------------------------------------------------------
# ПРОФИЛЬ: МАСТЕР
# ---------------------------------------------------------------------------


def start_profile_wizard_state(profile: Optional[sqlite3.Row]) -> Dict[str, Any]:
    state: Dict[str, Any] = {
        "step": PROFILE_STEP_PHOTO,
        "photo_file_ids": [],
        "name": None,
        "age": None,
        "faculty": None,
    }
    if profile:
        state["photo_file_ids"] = profile_photo_ids(profile)
        state["name"] = profile["name"]
        state["age"] = profile["age"]
        state["faculty"] = profile["faculty"]
    return state


async def start_profile_wizard_from_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    q = update.callback_query
    await q.answer()
    tg_user = q.from_user
    profile = db.get_profile(tg_user.id)
    context.user_data[UD_PROFILE_WIZARD] = start_profile_wizard_state(profile)

    existing_photos_count = len(profile_photo_ids(profile))
    existing_note = (
        f"\nСейчас в анкете сохранено {existing_photos_count} фото. "
        "Можешь оставить их или прислать новые."
        if existing_photos_count
        else ""
    )

    text = (
        "Начинаем создание / редактирование анкеты ✨\n\n"
        "1️⃣ Шаг 1: пришли до *трёх* своих фото, которые будут в анкете.\n"
        "Это должно быть обычное фото, где видно тебя.\n\n"
        "Когда закончишь, нажми «➡️ Дальше». В любой момент можно отменить командой /cancel."
        f"{existing_note}"
    )
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("➡️ Дальше", callback_data=PROFILE_PHOTOS_DONE)]]
    )
    await safe_edit(q, text, kb, parse_mode="Markdown")


async def handle_profile_photo_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    if not tg_user:
        return
    wizard = context.user_data.get(UD_PROFILE_WIZARD)
    if not wizard or wizard.get("step") != PROFILE_STEP_PHOTO:
        return
    if not update.message or not update.message.photo:
        await update.message.reply_text(
            "Я жду фото для анкеты 🙂 Отправь, пожалуйста, именно фотографию."
        )
        return
    photo = update.message.photo[-1]
    photos: List[str] = wizard.get("photo_file_ids", [])
# if len(photos) >= 3:
#     keyboard = [
#         [KeyboardButton("➡️ Дальше")]
#     ]
#     reply_markup = ReplyKeyboardMarkup(
#         keyboard,
#         resize_keyboard=True,
#         one_time_keyboard=True
#     )
# 
#     update.message.reply_text(
#         "Ты уже добавил три фото. Нажми «➡️ Дальше», чтобы перейти к заполнению анкеты.",
#         reply_markup=reply_markup
#     )
    
    photos.append(photo.file_id)
    wizard["photo_file_ids"] = photos
    context.user_data[UD_PROFILE_WIZARD] = wizard
    if len(photos) >= 3:
        wizard["step"] = PROFILE_STEP_NAME
        update.message.reply_text(
            "Отлично, сохранено три фото 💾\n\n"
            "2️⃣ Теперь напиши, пожалуйста, своё *имя* так, как хочешь видеть его в анкете.",
#             parse_mode="Markdown",
)
# 
#     remaining = 3 - len(photos)

# === FIXED PHOTO FLOW (1–3 photos) ===
photos = wizard.get("photo_file_ids", [])
remaining = 3 - len(photos)

if remaining <= 0:
    wizard["step"] = "name"
    await update.effective_message.reply_text(
        "Фото сохранены 🖼\n\nТеперь напиши своё имя так, как хочешь видеть его в анкете."
    )
    return

kb = InlineKeyboardMarkup([
    [InlineKeyboardButton("➡️ Дальше", callback_data="PROFILE_PHOTOS_DONE")]
])

await update.effective_message.reply_text(
    f"Фото сохранено 📸\nМожно добавить ещё {remaining} фото или нажми «➡️ Дальше».",
    reply_markup=kb
)

#     kb = InlineKeyboardMarkup(
#         [[InlineKeyboardButton("➡️ Дальше", callback_data=PROFILE_PHOTOS_DONE)]]
#     )
#     update.message.reply_text(
#         "Отлично, фото сохранено 💾\n\n"
#         f"Можешь добавить ещё {remaining} фото или нажми «➡️ Дальше», чтобы перейти к имени.",
#         reply_markup=kb,
# 
# 
# async def handle_profile_photos_done(update, context):
    q = getattr(update, 'callback_query', None)
    if q:
        await q.answer()
    wizard = context.user_data.get('wizard')
    if not wizard:
        return
    wizard['step'] = 'name'
    await update.effective_message.reply_text(
        "Фото сохранены 🖼

Теперь напиши своё имя так, как хочешь видеть его в анкете."
    )

async def  handle_profile_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    if not tg_user:
        return
    if not update.message or not update.message.text:
        return
    wizard = context.user_data.get(UD_PROFILE_WIZARD)
    if not wizard:
        return
    text = update.message.text.strip()
    step = wizard.get("step")

    if step == PROFILE_STEP_NAME:
        if len(text) < 2:
            await update.message.reply_text(
                "Имя слишком короткое. Напиши, пожалуйста, нормальное имя 🙂"
            )
            return
        wizard["name"] = text
        wizard["step"] = PROFILE_STEP_AGE
        context.user_data[UD_PROFILE_WIZARD] = wizard
        await update.message.reply_text(
            "Принял имя ✅\n\n3️⃣ Теперь напиши, пожалуйста, свой *возраст* цифрами.",
            parse_mode="Markdown",
        )
        return

    if step == PROFILE_STEP_AGE:
        if not text.isdigit():
            await update.message.reply_text("Возраст должен быть числом, без лишних символов.")
            return
        age = int(text)
        if age < 16 or age > 80:
            await update.message.reply_text(
                "Реальный ли это возраст? Напиши, пожалуйста, возраст от 16 до 80."
            )
            return
        wizard["age"] = age
        wizard["step"] = PROFILE_STEP_FACULTY
        context.user_data[UD_PROFILE_WIZARD] = wizard
        await update.message.reply_text(
            "Отлично, возраст записан ✅\n\n"
            "4️⃣ Напиши, пожалуйста, название твоего факультета (например, «МЭиМ», «МЖ» и т.п.)."
        )
        return

    if step == PROFILE_STEP_FACULTY:
        if len(text) < 2:
            await update.message.reply_text(
                "Название факультета слишком короткое. Напиши, пожалуйста, нормальное название."
            )
            return
        wizard["faculty"] = text
        wizard["step"] = PROFILE_STEP_CONFIRM
        context.user_data[UD_PROFILE_WIZARD] = wizard
        await send_profile_wizard_summary(update, context)
        return


async def send_profile_wizard_summary(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    wizard = context.user_data.get(UD_PROFILE_WIZARD)
    if not wizard:
        return
    photos: List[str] = wizard.get("photo_file_ids", [])
    name = wizard.get("name")
    age = wizard.get("age")
    faculty = wizard.get("faculty")

    text_lines = [
        "Почти готово! Проверим, всё ли ок 👇",
        "",
        f"Имя: {name}",
        f"Возраст: {age}",
        f"Факультет: {faculty}",
        "",
        "Если всё верно — жми «💾 Сохранить анкету».\n"
        "Если что-то не так, можно будет отредактировать позже.",
    ]
    text = "\n".join(text_lines)

    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💾 Сохранить анкету", callback_data="profile_save")],
            [InlineKeyboardButton("❌ Отмена", callback_data="profile_cancel")],
        ]
    )

    if update.message:
        if photos:
            await update.message.reply_photo(photo=photos[0], caption=text, reply_markup=kb)
        else:
            await update.message.reply_text(text, reply_markup=kb)
    elif update.callback_query:
        q = update.callback_query
        await q.answer()
        if photos:
            await q.message.reply_photo(photo=photos[0], caption=text, reply_markup=kb)
        else:
            await q.message.reply_text(text, reply_markup=kb)


async def handle_profile_save_or_cancel(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    q = update.callback_query
    await q.answer()
    data = q.data
    tg_user = q.from_user
    wizard = context.user_data.get(UD_PROFILE_WIZARD)

    if data == "profile_cancel":
        context.user_data.pop(UD_PROFILE_WIZARD, None)
        text = "Создание / редактирование анкеты отменено."
        await safe_edit(q, text, back_to_menu_keyboard())
        return

    if data == "profile_save":
        if not wizard:
            text = "Мастер анкеты не активен. Попробуй начать заново."
            await safe_edit(q, text, back_to_menu_keyboard())
            return

        photo_file_ids: List[str] = wizard.get("photo_file_ids", [])
        name = wizard.get("name")
        age = wizard.get("age")
        faculty = wizard.get("faculty")

        if not (photo_file_ids and name and age and faculty):
            text = "Не все данные заполнены. Попробуй снова запустить создание анкеты."
            await safe_edit(q, text, back_to_menu_keyboard())
            return

        existing = db.get_profile(tg_user.id)
        is_active = bool(existing["is_active"]) if existing else True

        db.upsert_profile(
            user_id=tg_user.id,
            photo_file_ids=photo_file_ids,
            name=name,
            age=int(age),
            faculty=faculty,
            is_active=is_active,
        )
        context.user_data.pop(UD_PROFILE_WIZARD, None)

        text = "Анкета сохранена ✅\n\nТеперь ты можешь просматривать анкеты и лайкать."
        await safe_edit(q, text, back_to_menu_keyboard())


# ---------------------------------------------------------------------------
# ВКЛ / ВЫКЛ АНКЕТЫ
# ---------------------------------------------------------------------------


async def handle_profile_toggle_active(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    q = update.callback_query
    await q.answer()
    data = q.data
    tg_user = q.from_user
    profile = db.get_profile(tg_user.id)

    if not profile:
        text = (
            "У тебя пока нет анкеты.\n\n"
            "Сначала создай её, а потом можно будет включать / выключать."
        )
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🚀 Создать анкету", callback_data="start_profile_wizard"
                    )
                ],
                [InlineKeyboardButton("⬅️ В главное меню", callback_data="back_to_menu")],
            ]
        )
        await safe_edit(q, text, kb)
        return

    if data == "profile_deactivate":
        db.set_profile_active(tg_user.id, False)
        text = (
            "Анкета *выключена* 🔴\n\n"
            "Теперь твоя анкета не показывается другим пользователям.\n"
            "Ты в любой момент можешь включить её обратно через «Моя анкета»."
        )
    else:  # profile_activate
        db.set_profile_active(tg_user.id, True)
        text = (
            "Анкета *включена* 🟢\n\n"
            "Теперь твоя анкета снова участвует в выдаче и показывается другим."
        )

    await safe_edit(q, text, back_to_menu_keyboard())


# ---------------------------------------------------------------------------
# ПОДПИСКА (YooKassa, 1 месяц)
# ---------------------------------------------------------------------------


async def show_subscription_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    if not tg_user:
        return
    row = db.ensure_user(tg_user)
    gender = row["gender"]

    # Тянем актуальный статус подписки с учётом окончания срока
    is_premium, sub_until, auto_renew = db.get_premium_info(tg_user.id)

    if gender == GENDER_FEMALE:
        text = (
            "Ты указала, что ты девушка 👩\n\n"
            "Для девушек в этом боте функционал *полностью бесплатен*.\n"
            "Можно сразу создавать анкету и листать других."
        )
        kb = back_to_menu_keyboard()
    elif gender == GENDER_MALE:
        if is_premium:
            human_until = sub_until.strftime("%d.%m.%Y") if sub_until else "неизвестно"
            auto_text = (
                "Автопродление: *включено* 🔁"
                if auto_renew
                else "Автопродление: *выключено* ⏹"
            )
            kb_buttons = [
                [
                    InlineKeyboardButton(
                        "⏹ Отменить автопродление",
                        callback_data="subscription_autorenew_off",
                    )
                ]
                if auto_renew
                else [
                    InlineKeyboardButton(
                        "🔁 Включить автопродление",
                        callback_data="subscription_autorenew_on",
                    )
                ],
                [InlineKeyboardButton("⬅️ В главное меню", callback_data="back_to_menu")],
            ]
            kb = InlineKeyboardMarkup(kb_buttons)
            text = (
                "Ты парень 👨 и у тебя сейчас *активна подписка* 💎\n\n"
                f"Подписка действует до: *{human_until}*\n"
                f"{auto_text}\n\n"
                "После окончания периода подписка может быть продлена "
                "ещё на месяц (в реальном продакшене это делает backend через YooKassa)."
            )
        else:
            text = (
                "Ты парень 👨.\n\n"
                "В этом боте просмотр анкет доступен по *месячной подписке* 💎.\n\n"
                f"Стоимость: *{SUBSCRIPTION_PRICE_RUB} ₽* за 1 месяц.\n\n"
                "Нажми кнопку ниже, чтобы оформить подписку через YooKassa.\n"
                "По умолчанию автопродление включено (ты можешь его потом отключить)."
            )
            kb = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            f"💳 Оплатить {SUBSCRIPTION_PRICE_RUB} ₽",
                            callback_data="subscription_pay",
                        )
                    ],
                    [InlineKeyboardButton("⬅️ В главное меню", callback_data="back_to_menu")],
                ]
            )
    else:
        text = (
            "Сначала нужно указать пол, чтобы я понял, как считать подписку.\n\n"
            "Выбери один из вариантов ниже."
        )
        kb = genders_keyboard()

    if update.callback_query:
        q = update.callback_query
        await q.answer()
        await safe_edit(q, text, kb)
    else:
        assert update.message
        await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


async def handle_subscription_pay(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Создаём платёж в YooKassa и отдаём пользователю ссылку.
    """
    q = update.callback_query
    await q.answer()
    tg_user = q.from_user

    logger.info("Creating YooKassa payment for user %s", tg_user.id)

    try:
        payment = Payment.create(
            {
                "amount": {
                    "value": SUBSCRIPTION_PRICE_RUB,
                    "currency": "RUB",
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": RETURN_URL,
                },
                "capture": True,
                "description": f"{SUBSCRIPTION_DESCRIPTION} for user {tg_user.id}",
                "metadata": {
                    "tg_user_id": str(tg_user.id),
                },
            }
        )
    except Exception as e:
        logger.exception("Error while creating YooKassa payment: %s", e)
        text = (
            "⚠️ Не удалось создать платёж в YooKassa.\n\n"
            "Попробуй ещё раз чуть позже или напиши админу."
        )
        await safe_edit(q, text, back_to_menu_keyboard())
        return

    payment_id = payment.id
    confirmation_url = payment.confirmation.confirmation_url

    context.user_data["last_payment_id"] = payment_id

    text = (
        "💳 Счёт на оплату создан.\n\n"
        f"Сумма: *{SUBSCRIPTION_PRICE_RUB} ₽* за 1 месяц.\n\n"
        "1. Нажми кнопку «🔗 Перейти к оплате» и оплати на сайте YooKassa.\n"
        "2. Вернись в бот и нажми «🔄 Проверить оплату».\n\n"
        "В этом коде дата окончания подписки сохраняется внутри бота.\n"
        "Реальное автоматическое списание по истечении срока должен делать backend."
    )

    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔗 Перейти к оплате", url=confirmation_url)],
            [
                InlineKeyboardButton(
                    "🔄 Проверить оплату",
                    callback_data=f"subscription_check_{payment_id}",
                )
            ],
            [InlineKeyboardButton("⬅️ В главное меню", callback_data="back_to_menu")],
        ]
    )

    await safe_edit(q, text, kb)


async def handle_subscription_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Проверяем статус платежа по payment_id.
    При успехе — даём подписку на 30 дней вперёд, auto_renew = True.
    """
    q = update.callback_query
    await q.answer()
    tg_user = q.from_user
    data = q.data

    prefix = "subscription_check_"
    payment_id = None

    if data.startswith(prefix):
        payment_id = data[len(prefix) :]
    else:
        payment_id = context.user_data.get("last_payment_id")

    if not payment_id:
        text = (
            "Не нашёл последний платёж.\n\n"
            "Попробуй снова создать подписку через раздел «Подписка»."
        )
        await safe_edit(q, text, back_to_menu_keyboard())
        return

    try:
        payment = Payment.find_one(payment_id)
    except Exception as e:
        logger.exception("Error while checking YooKassa payment: %s", e)
        text = (
            "⚠️ Не удалось проверить статус платежа.\n\n"
            "Если деньги списались — напиши админу, указав время платежа."
        )
        await safe_edit(q, text, back_to_menu_keyboard())
        return

    status = payment.status
    logger.info("Payment %s status for user %s: %s", payment_id, tg_user.id, status)

    if status == "succeeded":
        # даём подписку на 30 дней вперёд
        expires = datetime.utcnow() + timedelta(days=30)
        db.update_subscription(tg_user.id, True, expires, True)
        human_until = expires.strftime("%d.%m.%Y")
        text = (
            "🎉 Оплата прошла успешно, месячная подписка *активирована*!\n\n"
            f"Подписка действует до: *{human_until}*.\n"
            "Автопродление сейчас включено.\n\n"
            "Реальное списание в следующем месяце должен запускать backend "
            "через YooKassa по сохранённым данным, этот пример показывает только логику хранения."
        )
        await safe_edit(q, text, back_to_menu_keyboard())
    elif status in ("pending", "waiting_for_capture"):
        text = (
            "⏳ Платёж ещё не подтверждён.\n\n"
            "Если ты только что оплатил — подожди пару секунд и нажми "
            "«🔄 Проверить оплату» ещё раз."
        )
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🔄 Проверить ещё раз",
                        callback_data=f"subscription_check_{payment_id}",
                    )
                ],
                [InlineKeyboardButton("⬅️ В главное меню", callback_data="back_to_menu")],
            ]
        )
        await safe_edit(q, text, kb)
    else:
        text = (
            f"❌ Платёж имеет статус: *{status}*.\n\n"
            "Если ты уверен, что деньги списались, сделай скрин платежа и напиши админу."
        )
        await safe_edit(q, text, back_to_menu_keyboard())


async def handle_subscription_autorenew_toggle(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Включение/выключение автопродления с точки зрения логики бота.
    """
    q = update.callback_query
    await q.answer()
    tg_user = q.from_user
    data = q.data

    is_premium, sub_until, auto_renew = db.get_premium_info(tg_user.id)
    if not is_premium:
        text = (
            "У тебя сейчас нет активной подписки.\n\n"
            "Сначала оформи её в разделе «Подписка»."
        )
        await safe_edit(q, text, back_to_menu_keyboard())
        return

    if data == "subscription_autorenew_off":
        db.set_auto_renew(tg_user.id, False)
        human_until = sub_until.strftime("%d.%m.%Y") if sub_until else "неизвестно"
        text = (
            "⏹ Автопродление выключено.\n\n"
            f"Твоя текущая подписка действует до: *{human_until}*.\n"
            "После этой даты она не будет продлена автоматически.\n"
            "Если передумаешь — можешь включить автопродление снова."
        )
    else:  # subscription_autorenew_on
        db.set_auto_renew(tg_user.id, True)
        human_until = sub_until.strftime("%d.%m.%Y") if sub_until else "неизвестно"
        text = (
            "🔁 Автопродление включено.\n\n"
            f"Текущий оплаченный период до: *{human_until}*.\n"
            "С точки зрения логики бота подписка может продлеваться ежемесячно, "
            "но реальное списание должен запускать backend через YooKassa."
        )

    await safe_edit(q, text, back_to_menu_keyboard())


# ---------------------------------------------------------------------------
# ПРОСМОТР АНКЕТ / ЛАЙКИ / МЭТЧИ
# ---------------------------------------------------------------------------


async def ensure_can_browse(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> Optional[Tuple[str, bool]]:
    tg_user = update.effective_user
    if not tg_user:
        return None
    row = db.ensure_user(tg_user)
    gender = row["gender"]

    is_premium, sub_until, auto_renew = db.get_premium_info(tg_user.id)

    if gender not in (GENDER_MALE, GENDER_FEMALE):
        text = (
            "Перед просмотром анкет надо указать пол.\n\n"
            "Пожалуйста, выбери один из вариантов ниже."
        )
        kb = genders_keyboard()
        if update.callback_query:
            q = update.callback_query
            await q.answer()
            await safe_edit(q, text, kb)
        else:
            assert update.message
            await update.message.reply_text(text, reply_markup=kb)
        return None

    if not db.has_complete_profile(tg_user.id):
        text = (
            "Перед тем как листать анкеты, нужно сначала создать *свою* анкету 🙂\n\n"
            "Сейчас у тебя она не заполнена."
        )
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🚀 Создать анкету", callback_data="start_profile_wizard"
                    )
                ],
                [InlineKeyboardButton("⬅️ В главное меню", callback_data="back_to_menu")],
            ]
        )
        if update.callback_query:
            q = update.callback_query
            await q.answer()
            await safe_edit(q, text, kb)
        else:
            assert update.message
            await update.message.reply_text(text, reply_markup=kb)
        return None

    if gender == GENDER_MALE and not is_premium:

        views = db.get_daily_views(tg_user.id)

        if views >= 3:
            text = text = """💎 Доступ ограничен

Ты посмотрел 3 анкеты.

Чтобы продолжить — оформи подписку."""
            kb = InlineKeyboardMarkup(

                [

                    [InlineKeyboardButton("💎 Подписка", callback_data="subscription")],

                    [InlineKeyboardButton("⬅️ В главное меню", callback_data="back_to_menu")],

                ]

            )

            if update.callback_query:

                q = update.callback_query

                await q.answer()

                await safe_edit(q, text, kb)

            else:

                assert update.message

                await update.message.reply_text(text, reply_markup=kb)

            return None

    return gender, is_premium


async def show_next_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    can = await ensure_can_browse(update, context)
    if not can:
        return

    gender, is_premium = can
    tg_user = update.effective_user
    if not tg_user:
        return

    candidate = db.get_next_candidate_for(tg_user.id, gender)
    if not candidate:
        text = (
            "На данный момент я не нашёл новых анкет для тебя 😔\n\n"
            "Попробуй зайти позже — кто-нибудь обязательно появится!"
        )
        if update.callback_query:
            q = update.callback_query
            await q.answer()
            await safe_edit(q, text, back_to_menu_keyboard())
        else:
            assert update.message
            await update.message.reply_text(text, reply_markup=back_to_menu_keyboard())
        return

    caption = (
        f"Имя: {candidate['name']}\n"
        f"Возраст: {candidate['age']}\n"
        f"Факультет: {candidate['faculty']}"
    )
    photos = profile_photo_ids(candidate)
    kb = browse_profile_keyboard(candidate["user_id"])

    if update.callback_query:
        q = update.callback_query
        await q.answer()
        await send_photos_with_caption(
            context.bot, q.from_user.id, photos, caption, kb
        )

    if gender == GENDER_MALE and not is_premium:
        db.inc_daily_views(tg_user.id)
        await safe_edit(q, "Новая анкета отправлена выше 👆", back_to_menu_keyboard())
    else:
        assert update.message
        await send_photos_with_caption(
            context.bot, tg_user.id, photos, caption, kb
        )


    if gender == GENDER_MALE and not is_premium:
        db.inc_daily_views(tg_user.id)

async def handle_browse_profiles_entry(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    await show_next_profile(update, context)


async def handle_like_or_dislike(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    data = q.data
    tg_user = q.from_user

    if data.startswith("like_"):
        target_id_str = data.split("_", 1)[1]
        is_like = True
    elif data.startswith("dislike_"):
        target_id_str = data.split("_", 1)[1]
        is_like = False
    else:
        return

    try:
        target_user_id = int(target_id_str)
    except ValueError:
        text = "Ошибка: некорректный ID анкеты."
        await safe_edit(q, text, back_to_menu_keyboard())
        return

    db.set_like(tg_user.id, target_user_id, is_like)

    if not is_like:
        await show_next_profile(update, context)
        return

    # лайк
    if db.has_mutual_like(tg_user.id, target_user_id):
        viewer_username = db.get_username(tg_user.id)
        target_username = db.get_username(target_user_id)
        viewer_contact = f"@{viewer_username}" if viewer_username else f"id {tg_user.id}"
        target_contact = f"@{target_username}" if target_username else f"id {target_user_id}"

        try:
            await context.bot.send_message(
                chat_id=tg_user.id,
                text=(
                    "✨ У тебя новый мэтч! ✨\n\n"
                    f"Вы понравились друг другу с пользователем {target_contact}.\n"
                    "Можешь написать ему(ей) в Telegram."
                ),
            )
        except Exception as e:
            logger.warning("Не удалось отправить сообщение о матче viewer: %s", e)

        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=(
                    "✨ У тебя новый мэтч! ✨\n\n"
                    f"Вы понравились друг другу с пользователем {viewer_contact}.\n"
                    "Можешь написать ему(ей) в Telegram."
                ),
            )
        except Exception as e:
            logger.warning("Не удалось отправить сообщение о матче target: %s", e)

        await show_next_profile(update, context)
        return

    # лайк без мэтча → просто идём дальше
    await show_next_profile(update, context)


# ---------------------------------------------------------------------------
# КОМАНДЫ
# ---------------------------------------------------------------------------


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    if tg_user:
        db.ensure_user(tg_user)

    text = (
        "Ты в MGIMO Dating Club — закрытом элитном сообществе знакомств внутри МГИМО.\n\n"
        "Девушки попадают сюда бесплатно и первыми.\n"
        "Мужчины — только по вступительному взносу, что гарантирует высокий уровень участников.\n\n"
        "Это пространство стиля, приватности и выбора.\n"
        "Начни прямо сейчас 👇"
    )

    assert update.message
    await update.message.reply_text(text, reply_markup=main_menu_keyboard())


async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_main_menu(update, context)


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop(UD_PROFILE_WIZARD, None)
    assert update.message
    await update.message.reply_text(
        "Все текущие операции отменены. Возвращаю в главное меню.",
        reply_markup=main_menu_keyboard(),
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "Немного о том, как пользоваться ботом:\n\n"
        "1️⃣ Укажи свой пол (если бот попросит).\n"
        "2️⃣ Создай анкету: фото, имя, возраст, факультет.\n"
        "3️⃣ Если ты парень — оформи *месячную подписку*.\n"
        "4️⃣ Нажимай «Смотреть анкеты», листай профили и ставь лайки.\n"
        "5️⃣ При взаимном лайке получите друг друга в Telegram ✨\n"
        "6️⃣ Анкету можно *включать/выключать* в разделе «Моя анкета».\n"
        "7️⃣ Подписка имеет срок действия и может автопродлеваться (с точки зрения логики бота).\n\n"
        "Реальное автоматическое списание денег по окончании месяца "
        "нужно реализовывать на backend'е через YooKassa."
    )
    assert update.message
    await update.message.reply_text(text)


async def handle_help_from_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    text = (
        "Немного о том, как пользоваться ботом:\n\n"
        "1️⃣ Укажи свой пол (если бот попросит).\n"
        "2️⃣ Создай анкету: фото, имя, возраст, факультет.\n"
        "3️⃣ Если ты парень — оформи *месячную подписку*.\n"
        "4️⃣ Нажимай «Смотреть анкеты», листай профили и ставь лайки.\n"
        "5️⃣ При взаимном лайке получите контакты друг друга ✨\n"
        "6️⃣ Анкету можно *включать/выключать* в разделе «Моя анкета».\n"
        "7️⃣ Подписку можно автопродлевать/отключать автопродление.\n\n"
        "По всем возникшим вопросам обращаться к @liahandro.\n"
    )
    await safe_edit(q, text, back_to_menu_keyboard())


# ---------------------------------------------------------------------------
# РЕДАКТИРОВАНИЕ ОТДЕЛЬНЫХ ПОЛЕЙ ПРОФИЛЯ
# ---------------------------------------------------------------------------


async def handle_edit_profile_field(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    data = q.data
    tg_user = q.from_user
    profile = db.get_profile(tg_user.id)

    if not profile:
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🚀 Создать анкету", callback_data="start_profile_wizard"
                    )
                ],
                [InlineKeyboardButton("⬅️ В главное меню", callback_data="back_to_menu")],
            ]
        )
        text = (
            "У тебя пока нет сохранённой анкеты. "
            "Давай сначала создадим её с нуля."
        )
        await safe_edit(q, text, kb)
        return

    wizard = start_profile_wizard_state(profile)

    if data == "edit_profile_photo":
        wizard["step"] = PROFILE_STEP_PHOTO
        text = (
            "Ок, давай обновим фото 📸\n\n"
            "Пришли до трёх новых фото для анкеты или нажми «➡️ Дальше», "
            "если хочешь оставить текущие. В любой момент можно отменить командой /cancel."
        )
    elif data == "edit_profile_name":
        wizard["step"] = PROFILE_STEP_NAME
        text = (
            "Изменим имя 📝\n\n"
            "Напиши новое имя, которое хочешь видеть в анкете.\n"
            f"Сейчас: {profile['name']}"
        )
    elif data == "edit_profile_age":
        wizard["step"] = PROFILE_STEP_AGE
        text = (
            "Изменим возраст 🎂\n\n"
            "Напиши свой возраст цифрами.\n"
            f"Сейчас: {profile['age']}"
        )
    elif data == "edit_profile_faculty":
        wizard["step"] = PROFILE_STEP_FACULTY
        text = (
            "Изменим факультет 🏫\n\n"
            "Напиши новое название факультета.\n"
            f"Сейчас: {profile['faculty']}"
        )
    else:
        text = "Неизвестное действие редактирования."
        await safe_edit(q, text, back_to_menu_keyboard())
        return

    context.user_data[UD_PROFILE_WIZARD] = wizard
    kb = None
    if wizard.get("step") == PROFILE_STEP_PHOTO:
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("➡️ Дальше", callback_data=PROFILE_PHOTOS_DONE)]]
        )
    await safe_edit(q, text, kb, parse_mode="Markdown")


# ---------------------------------------------------------------------------
# CALLBACK РОУТЕР
# ---------------------------------------------------------------------------


async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    data = q.data

    if data == "back_to_menu":
        await send_main_menu(update, context)
        return
    if data in ("gender_male", "gender_female"):
        await handle_gender_choice(update, context)
        return
    if data == "view_profile":
        await send_profile_view(update, context)
        return
    if data == "edit_profile":
        tg_user = q.from_user
        profile = db.get_profile(tg_user.id)
        if not profile or not db.has_complete_profile(tg_user.id):
            await start_profile_wizard_from_callback(update, context)
        else:
            await send_profile_view(update, context)
        return
    if data == "start_profile_wizard":
        await start_profile_wizard_from_callback(update, context)
        return
    if data == PROFILE_PHOTOS_DONE:
        await handle_profile_photos_done(update, context)
        return
    if data == "subscription":
        await show_subscription_info(update, context)
        return
    if data == "subscription_pay":
        await handle_subscription_pay(update, context)
        return
    if data.startswith("subscription_check_"):
        await handle_subscription_check(update, context)
        return
    if data in ("subscription_autorenew_off", "subscription_autorenew_on"):
        await handle_subscription_autorenew_toggle(update, context)
        return
    if data in ("browse_profiles", "next_profile"):
        await handle_browse_profiles_entry(update, context)
        return
    if data.startswith("edit_profile_"):
        await handle_edit_profile_field(update, context)
        return
    if data in ("profile_save", "profile_cancel"):
        await handle_profile_save_or_cancel(update, context)
        return
    if data in ("profile_activate", "profile_deactivate"):
        await handle_profile_toggle_active(update, context)
        return
    if data.startswith("like_") or data.startswith("dislike_"):
        await handle_like_or_dislike(update, context)
        return
    if data == "help":
        await handle_help_from_callback(update, context)
        return

    await q.answer("Неизвестное действие.", show_alert=True)


# ---------------------------------------------------------------------------
# FALLBACK-ОБРАБОТЧИКИ
# ---------------------------------------------------------------------------


async def handle_unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message
    await update.message.reply_text(
        "Я не знаю такую команду. Попробуй /menu или /help."
    )


async def handle_fallback_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    wizard = context.user_data.get(UD_PROFILE_WIZARD)
    if wizard:
        return
    assert update.message
    await update.message.reply_text(
        "Не до конца понял, что ты хочешь 🤔\n"
        "Пользуйся, пожалуйста, кнопками или командами.\n\n"
        "Открываю главное меню:",
        reply_markup=main_menu_keyboard(),
    )


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------


def main() -> None:
    token = BOT_TOKEN or os.getenv("TELEGRAM_BOT_TOKEN")
    if not token or token == "PASTE_YOUR_TELEGRAM_BOT_TOKEN_HERE":
        raise RuntimeError("Укажи токен бота в BOT_TOKEN или TELEGRAM_BOT_TOKEN")

    app: Application = ApplicationBuilder().token(token).build()

    # команды
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("menu", cmd_menu))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CommandHandler("help", cmd_help))

    # мастер анкеты
    app.add_handler(
        MessageHandler(filters.PHOTO & (~filters.COMMAND), handle_profile_photo_message)
    )
    app.add_handler(
        MessageHandler(filters.TEXT & (~filters.COMMAND), handle_profile_text_message)
    )

    # callback'и
    app.add_handler(CallbackQueryHandler(callback_router))

    # неизвестные команды и текст
    app.add_handler(MessageHandler(filters.COMMAND, handle_unknown_command))
    app.add_handler(MessageHandler(filters.TEXT, handle_fallback_text))

    logger.info("Bot started. Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()

    def get_daily_views(self, user_id: int) -> int:
        conn = self._connect()
        c = conn.cursor()
        c.execute(
            "SELECT COALESCE(daily_views, 0) FROM users WHERE user_id = ?",
            (user_id,)
        )
        row = c.fetchone()
        conn.close()
        return int(row[0]) if row and row[0] is not None else 0

    def inc_daily_views(self, user_id: int) -> None:
        conn = self._connect()
        c = conn.cursor()
        c.execute(
            "UPDATE users SET daily_views = COALESCE(daily_views, 0) + 1, updated_at = ? WHERE user_id = ?",
            (self._now(), user_id)
        )
        conn.commit()
        conn.close()



# ================== RUNTIME DAILY VIEWS PATCH ==================
# НЕ УДАЛЯТЬ. Гарантирует наличие методов у Database во всех местах.
__RUNTIME_DAILY_VIEWS_PATCH__ = True

def _db_get_daily_views(self, user_id: int) -> int:
    conn = self._connect()
    c = conn.cursor()
    try:
        c.execute("SELECT COALESCE(daily_views, 0) FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()

def _db_inc_daily_views(self, user_id: int, delta: int = 1) -> None:
    conn = self._connect()
    c = conn.cursor()
    try:
        c.execute(
            "UPDATE users SET daily_views = COALESCE(daily_views, 0) + ? WHERE user_id = ?",
            (delta, user_id)
        )
        conn.commit()
    finally:
        conn.close()

# принудительно навешиваем методы на Database
Database.get_daily_views = _db_get_daily_views
Database.inc_daily_views = _db_inc_daily_views
# ================== END PATCH ==================
