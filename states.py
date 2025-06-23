from aiogram.dispatcher.filters.state import State, StatesGroup


class ReportStates(StatesGroup):
    choosing_region = State()
    choosing_partner = State()
    choosing_year = State()
    confirmation = State()
    choosing_digit_settings = State()
    choosing_category_settings = State()
    choosing_subcategory_settings = State()
    choosing_months_settings = State()
    choosing_table_size_settings = State()
