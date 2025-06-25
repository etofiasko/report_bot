import sys
import os
from io import BytesIO
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from states import ReportStates
from bot_db import get_regions, get_partners, get_years, register_user, add_download_history, get_categories, get_subcategories
from config import REPORT_MODULE_PATH

sys.path.insert(0, REPORT_MODULE_PATH)

from document_gen.generator import generate_trade_document

# async def start_handler(message: types.Message, state: FSMContext, user=None):
#     await state.finish()
#     user = user or message.from_user
#     telegram_id = user.id
#     username = user.username or f"user_{telegram_id}"
#     register_user(telegram_id, username)

#     regions = get_regions()
#     if not regions:
#         await message.reply("На данный момент нет доступных данных.")
#         await start_handler(message, state)
#         return
    
#     keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
#     keyboard.add(KeyboardButton("Отмена"))
#     # for region in regions:
#     #     keyboard.add(KeyboardButton(region))
#     keyboard.add(KeyboardButton("Республика Казахстан"))
#     await message.answer(f"Добро пожаловать {username}.\n\nВыберите регион:", reply_markup=keyboard)
#     await ReportStates.choosing_region.set()


async def start_handler(message: types.Message, state: FSMContext, user=None):
    await state.finish()
    user = user or message.from_user
    telegram_id = user.id
    username = user.username or f"user_{telegram_id}"
    register_user(telegram_id, username)

    region = "Республика Казахстан"
    partners = get_partners(region)
    if not partners:
        await message.reply("Для этого региона нет данных по странам-партнёрам.")
        return

    await state.update_data(region=region)

    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for partner in partners:
        keyboard.add(KeyboardButton(partner))

    await message.answer(
        f"Добро пожаловать {username}.\n\nВыберите страну-партнёра для региона: {region}.",
        reply_markup=keyboard
    )
    await ReportStates.choosing_partner.set()


async def region_chosen_handler(message: types.Message, state: FSMContext):
    text = message.text.strip()
    region = message.text.strip()
    
    if region.lower() == "отмена":
        await start_handler(message, state)
        return

    partners = get_partners(region)
    if not partners:
        await message.reply("Для этого региона нет данных по странам-партнёрам. Попробуйте выбрать другой регион.")
        await start_handler(message, state)
        return

    await state.update_data(region=region.strip())
    
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(KeyboardButton("Отмена"))
    for partner in partners:
        keyboard.add(KeyboardButton(partner))

    await message.answer("Выберите страну-партнёра:", reply_markup=keyboard)
    await ReportStates.choosing_partner.set()


async def partner_chosen_handler(message: types.Message, state: FSMContext):
    text = message.text.strip()
    partner = message.text.strip()
    
    if partner.lower() == "отмена":
        await start_handler(message, state)
        return

    user_data = await state.get_data()
    region = user_data.get("region")
    partners = get_partners(region)

    if text not in partners:
        await message.answer("Такого партнёра нет. Пожалуйста, выберите из предложенного списка.")
        return

    years = get_years(region, partner)
    if not years:
        await message.reply("Для этого региона и страны-партнёра нет данных по годам. Попробуйте выбрать другой регион.")
        await start_handler(message, state)
        return

    await state.update_data(partner=partner.strip())

    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(KeyboardButton("Отмена"))
    for year in years:
        keyboard.add(KeyboardButton(year))

    await message.answer("Выберите год:", reply_markup=keyboard)
    await ReportStates.choosing_year.set()


async def year_chosen_handler(message: types.Message, state: FSMContext):
    year = message.text.strip()
    
    if year.lower() == "отмена":
        await start_handler(message, state)
        return

    await state.update_data(year=year.strip())

    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("Подтвердить выбор", callback_data="confirm"),
        InlineKeyboardButton("Расширенные настройки", callback_data="advanced_settings"),
        InlineKeyboardButton("Отмена", callback_data="cancel")
    )

    await message.answer(
        f"Вы выбрали:\n"
        f"Регион: <b>{(await state.get_data()).get('region')}</b>\n"
        f"Страна-партнёр: <b>{(await state.get_data()).get('partner')}</b>\n"
        f"Год: <b>{year}</b>\n\n"
        f"Пожалуйста, подтвердите выбор или настройте дополнительные параметры:",
        parse_mode='HTML',
        reply_markup=keyboard
    )
    await ReportStates.confirmation.set()


async def confirmation_handler(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer()
    await callback_query.message.edit_reply_markup(reply_markup=None)

    if callback_query.data == "cancel":
        user_message = callback_query.from_user
        await start_handler(callback_query.message, state, user=user_message)
        return

    if callback_query.data == "confirm":
        await finalize_report(callback_query, state, callback_query.from_user)
        return

    if callback_query.data == "advanced_settings":
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add(KeyboardButton("Отмена"))
        keyboard.add(KeyboardButton("4 знака (По умолчанию)"))
        keyboard.add(KeyboardButton("6 знаков"))
        await callback_query.message.answer(
            "Введите количество знаков 4 или 6:",
            reply_markup=keyboard
        )
        await ReportStates.choosing_digit_settings.set()


async def digit_settings_handler(message: types.Message, state: FSMContext):
    text = message.text.strip()
    if message.text.lower() == "отмена":
        await start_handler(message, state)
        return
    
    if message.text.strip() == "4 знака (По умолчанию)":
            message.text = '4'
    elif message.text.strip() == "6 знаков":
            message.text = '6'
    else:
        if not text.isdigit():
            await message.answer("Пожалуйста, введите **число** 4 или 6 или нажмите 'Отмена'.")
            return

        value = int(text)
        if value != 4 and value != 6:
            await message.answer("Число должно быть 4 или 6. Попробуйте ещё раз.")
            return


    await state.update_data(digit=message.text.strip())
    
    categories = get_categories()

    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(KeyboardButton("Отмена"))
    keyboard.add(KeyboardButton("Нет категории (По умолчанию)"))
    for category in categories:
        keyboard.add(KeyboardButton(category))
    await message.answer(
        "Введите категорию или по умолчанию (Нет категории):",
        reply_markup=keyboard
    )
    await ReportStates.choosing_category_settings.set()


async def category_settings_handler(message: types.Message, state: FSMContext):
    text = message.text.strip()
    if message.text.lower() == "отмена":
        await start_handler(message, state)
        return
    

    if text.strip().startswith("Нет категории (По умолчанию)"):
        await state.update_data(category='', subcategory='')
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add(KeyboardButton("Отмена"))
        keyboard.add(KeyboardButton("1, 12 (По умолчанию)"))

        await message.answer(
            "Введите нужный месяц в формате X или диапазон месяцев в формате X, Y. По умолчанию (1, 12):",
            reply_markup=keyboard
        )
        await ReportStates.choosing_months_settings.set()
        return
    categories = get_categories()
    if text not in categories:
            await message.answer("Такой категории нет. Пожалуйста, выберите из предложенного списка.")
            return
    

    subcats = get_subcategories(text)

    if not subcats:
        await state.update_data(category='', subcategory='')
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add(KeyboardButton("Отмена"))
        keyboard.add(KeyboardButton("1, 12 (По умолчанию)"))

        await message.answer(
            "Введите нужный месяц в формате X или диапазон месяцев в формате X, Y. По умолчанию (1, 12):",
            reply_markup=keyboard
        )
        await ReportStates.choosing_months_settings.set()
        return

    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(KeyboardButton("Отмена"))
    for sc in subcats:
        keyboard.add(KeyboardButton(sc))
    await state.update_data(category=text)
    await message.answer(
        "Введите подкатегорию:",
        reply_markup=keyboard
    )
    await ReportStates.choosing_subcategory_settings.set()


async def subcategory_settings_handler(message: types.Message, state: FSMContext):
    text = message.text.strip()
    if message.text.lower() == "отмена":
        await start_handler(message, state)
        return
    data = await state.get_data()
    category = data.get("category")
    subcategories = get_subcategories(category)
    if text not in subcategories:
            await message.answer("Такой подкатегории нет. Пожалуйста, выберите из предложенного списка.")
            return

    await state.update_data(subcategory=message.text.strip())

    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(KeyboardButton("Отмена"))
    keyboard.add(KeyboardButton("1, 12 (По умолчанию)"))

    await message.answer(
        "Введите нужный месяц в формате X или диапазон месяцев в формате X, Y. По умолчанию (1, 12):",
        reply_markup=keyboard
    )
    await ReportStates.choosing_months_settings.set()


async def months_settings_handler(message: types.Message, state: FSMContext):
    text = message.text.strip()
    if message.text.lower() == "отмена":
        await start_handler(message, state)
        return
    
    if message.text.strip() == "1, 12 (По умолчанию)":
        text = ''
    else:
        if "," in text:
            try:
                start, end = map(int, text.split(","))
                if not (1 <= start <= 12 and 1 <= end <= 12):
                    await message.answer("Месяцы должны быть от 1 до 12.")
                    return
                if end < start:
                    await message.answer("Конечный месяц не может быть меньше начального.")
                    return
                if start == end:
                    await message.answer("Начальный и конечный месяц не должны быть одинаковыми.")
                    return
            except ValueError:
                await message.answer("Неверный формат месяцев. Убедитесь, что вы ввели два числа через запятую.")
                return
        else:
            if not text.isdigit():

                await message.answer("Введите нужный месяц в формате X или диапазон месяцев в формате X, Y. По умолчанию (1, 12):")
                return

            month = int(text)
            if not (1 <= month <= 12):
                await message.answer("Месяц должен быть от 1 до 12.")
                return

    await state.update_data(months=text.strip().replace(" ", ""))
    
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(KeyboardButton("Отмена"))
    keyboard.add(KeyboardButton("25 (По умолчанию)"))
    await message.answer(
        "Введите количество строк от 10 до 50 или по умолчанию (25):",
        reply_markup=keyboard
    )
    await ReportStates.choosing_table_size_settings.set()


async def table_size_settings_handler(message: types.Message, state: FSMContext):
    text = message.text.strip()
    if message.text.lower() == "отмена":
        await start_handler(message, state)
        return
    
    if message.text.strip() == "25 (По умолчанию)":
        text = ''
    else:
        if not text.isdigit():
            await message.answer("Пожалуйста, введите **число** от 10 до 50 или нажмите 'Отмена'.")
            return

        value = int(text)
        if value < 10 or value > 50:
            await message.answer("Число должно быть **в диапазоне от 10 до 50**. Попробуйте ещё раз.")
            return

    await state.update_data(table_size=text)
    await finalize_report(message, state, message.from_user)


async def finalize_report(msg_or_cbq, state, tg_user):
    data = await state.get_data()

    region = str(data["region"])
    partner = str(data["partner"])
    year = int(data["year"])
    digit = int(data.get("digit") or 4)
    subcategory = (data.get("subcategory") or None)
    months = str(data.get("months") or "")
    table_size = int(data.get("table_size") or 25)
    try:
        doc, filename = generate_trade_document(
            region=region,
            country_or_group=partner,
            year=year,
            digit=digit,
            category=subcategory,
            table_size=table_size,
            month_range_raw=months,
        )

    except RuntimeError as e:
        await msg_or_cbq.answer(str(e))
        return
    if filename != 'Данных нет':
        await msg_or_cbq.answer(f"Идет генерация отчета. Пожалуйста, подождите.")
        buf = BytesIO()
        doc.save(buf)
        buf.seek(0)

        if isinstance(msg_or_cbq, types.CallbackQuery):
            await msg_or_cbq.message.answer_document((filename, buf))
            await msg_or_cbq.message.answer(f"Ваш документ {filename} готов. Чтобы начать заново, нажмите /start")
        else:
            await msg_or_cbq.answer_document((filename, buf))
            await msg_or_cbq.answer(f"Ваш документ {filename} готов. Чтобы начать заново, нажмите /start")

        await add_download_history(tg_user.id, tg_user.username, region, partner, year)
        await state.finish()
    else:
        if isinstance(msg_or_cbq, types.CallbackQuery):
            await msg_or_cbq.message.answer(f"По выбранным фильтрам нет данных. Чтобы начать заново, нажмите /start")
        else:
            await msg_or_cbq.answer(f"По выбранным фильтрам нет данных. Чтобы начать заново, нажмите /start")
        await state.finish()