from aiogram.fsm.state import State, StatesGroup

class ChatState(StatesGroup):
    waiting_for_nickname = State()
    waiting_for_partner = State()
    waiting_for_link_activation = State()
    in_chat = State()
    selecting_chat = State()
    managing_users = State() 