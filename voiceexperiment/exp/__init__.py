from calendar import week
from otree.api import *
import random
from random import randint
import json


doc = """
voice experiment
"""


class C(BaseConstants):
    NAME_IN_URL = 'exp'
    PLAYERS_PER_GROUP = None
    NUM_ROUNDS = 24

    key_treatment = 'treatment_words'
    key_q_params_pairs = 'questionaire_parameters_pairs'
    key_selected_q = 'selected_questionaire'


class Subsession(BaseSubsession):
    pass


class Group(BaseGroup):
    pass


class Player(BasePlayer):
    # GetMoneyNowOrFuture
    waiting_period = models.IntegerField() # 幾週後 (hidden)
    gained_amount = models.IntegerField() # 獲得的報償 (hidden)
    treatment_words = models.StringField(initial = '') # treatment(will be paid, paid)
    get_money_now_or_future = models.StringField(label = 'Please choose if you would like to receive the payment today or in the future.', widget = widgets.RadioSelect,  choices = [['now', 'I choose to receive the payment today'], ['future','I choose to receive the payment in the future']])
    get_money_now_or_future_test = models.StringField(label = 'Please choose if you would like to receive the payment today or in the future.', widget = widgets.RadioSelect, choices = [['now', 'I choose to receive the payment today'], ['future','I choose to receive the payment in the future']]) # 因為是範例，所以作答結果不記在記錄正式實驗的field
    treatment_number = models.IntegerField() # 1: will be paid, 2: paid

    num_listen_times = models.IntegerField(initial = 0) # 聽了幾次，單位為次數 (hidden，根據使用者行為紀錄)
    decision_duration = models.FloatField(initial = 0) # 決策時長，單位為秒數 (hidden，根據使用者行為紀錄)
    is_selected = models.BooleanField(initial = False) # 是否為最後電腦選中的 round (hidden，最後一回合會抽出並寫入)
   
    # Payoff account
    account = models.StringField(label = "Please fill in your account")

    # Survey
    gender = models.StringField(label = "1. What is your gender?", widget = widgets.RadioSelect, choices = ["Male", "Female", "Not above"])
    bloodgroup = models.StringField(label = "2. What is your blood type?", widget = widgets.RadioSelect, choices = ["Type A", "Type B", "Type AB", "Type O", "Unknown", "None of above"])
    taiwanese = models.StringField(label = "3. Are you a local Taiwanese student?", widget = widgets.RadioSelect, choices = ["Local Taiwanese student", "Non-local Taiwanese student (e.g. overseas Chinese student, exchange student)"])
    econ_manage = models.StringField(label = "4. Are you an economics or business major?", widget = widgets.RadioSelect, choices = ["Yes", "No"])
    class_num = models.StringField(label = "5. How many economics courses have you taken?", widget = widgets.RadioSelect, choices = ["0 course", "1 course", "2 courses", "3 courses", "4 courses", "5 courses", "more than 5 courses"])
    grade = models.StringField(label = "6. What year are you in, in college?", widget = widgets.RadioSelect, choices = ["Year 1", "Year 2", "Year 3", "Year 4", "Year 5 or above", "Graduate student"])
    guess = models.LongStringField(label = "7. Would you please guess the purpose of the experiment and write it down here?")



# Treat
class WaitingPeriod(object):
    list = [1, 4, 12]

class GainedAmount(object):
    list = [105, 110, 115, 120, 125, 130, 135, 140]
    today = 100

class Treatment(object):    
    participant_ids = []

    def prepare_participant_ids_if_needed(all_players):
        Treatment.participant_ids.clear()
        for p in all_players:
            pid = p.id_in_subsession
            if pid not in Treatment.participant_ids:
                Treatment.participant_ids.append(pid)    

    available_list = ['will be paid', 'paid']
    list = []

    def prepare_list(all_players): # 事先準備好所有受試者的treatment
        Treatment.list.clear()
        Treatment.prepare_participant_ids_if_needed(all_players)
        count = int(len(Treatment.participant_ids) / len(Treatment.available_list)) # 例如有5人，平均分配兩組 treatment，那就是 5/2 = 2（不取餘數）
        for each_option in Treatment.available_list:
            for i in range(count):
                Treatment.list.append(each_option)
        while len(Treatment.list) < len(Treatment.participant_ids): # 若因前面 for 迴圈中不能整除，也就是 `speech_speed_list` 不能完平均地分配給所有 participants，則最後會不夠，在此補上。（如果 `speed_available_list` 就兩個，那最多就差1，也就是最多會差到(count - 1)個）
            Treatment.list.append(random.choice(Treatment.available_list)) # 剩下的就隨機挑選
        random.shuffle(Treatment.list) # 打亂原有 list 順序


# FUNCTIONS
def creating_session(subsession):
    if subsession.round_number == 1:
        Treatment.prepare_participant_ids_if_needed(subsession.get_players())
        Treatment.prepare_list(subsession.get_players())
        for player in subsession.get_players():
            participant = player.participant
            pid = participant.id_in_session - 1
            player.treatment_words = Treatment.list[pid]
            if player.treatment_words == "will be paid":
                player.treatment_number = 1
            else:
                player.treatment_number = 2


def generate_questionaire_parameters_pairs():
    q_params_pairs = []
    # 產生所有週數和金額的組合
    shuffled_waiting_period = WaitingPeriod.list
    random.shuffle(shuffled_waiting_period) # 打亂順序
    for each_waiting_period in shuffled_waiting_period:
        for each_gained_amount in GainedAmount.list:
            q_params_pairs.append(
            dict(
            waiting_period =  each_waiting_period,
            gained_amount = each_gained_amount,
            )
        )
    return q_params_pairs

def setup_questionaire_parameters_pairs(player):
    # 如果還不存在，就現在產生「週數和金額的組合」並存起來
    # 如果已經存在，就取出
    if C.key_q_params_pairs not in player.participant.vars: 
        pairs = generate_questionaire_parameters_pairs()
        player.participant.vars[C.key_q_params_pairs] = pairs
    q_params_pairs = player.participant.vars[C.key_q_params_pairs]

    # 設定每一 round 的參數，並寫入 db
    idx = player.round_number - 1 # list 從0開始 但 round_number 從1開始
    pair = q_params_pairs[idx]
    player.waiting_period = pair['waiting_period']
    player.gained_amount = pair['gained_amount']

# 選其中一回合，實現報酬
def select_questionaire(player):
    q_params_pairs = player.participant.vars[C.key_q_params_pairs]
    selected_idx = randint(1, C.NUM_ROUNDS) - 1 # list 的 index 從0開始 但 round_number 從1開始
    selected_q_parama_pair = q_params_pairs[selected_idx]
    selected_player = player.in_all_rounds()[selected_idx]
    selected_player.is_selected = True
    player.participant.vars[C.key_selected_q] = dict(
        selected_round_number = selected_idx + 1,
        selected_waiting_period = selected_q_parama_pair['waiting_period'],
        selected_gained_amount = selected_q_parama_pair['gained_amount'],
        selected_get_money_now = selected_player.get_money_now_or_future == 'now',
        )


# PAGES
class Intro1(Page):
    @staticmethod
    def is_displayed(player):
        return player.round_number == 1

class Intro2(Page):
    @staticmethod
    def is_displayed(player):
        return player.round_number == 1

class Intro3(Page):
    form_model = 'player'
    form_fields = ['treatment_words', 'get_money_now_or_future_test']

    @staticmethod
    def vars_for_template(player):
        return {
            "treatment_words": player.treatment_words,
            "audio": '120_2_{}.m4a'.format(player.treatment_number)
	    }    
    @staticmethod
    def is_displayed(player):
        return player.round_number == 1

class Intro4(Page):
    @staticmethod
    def is_displayed(player):
        return player.round_number == 1

class Intro5(Page):
    @staticmethod
    def is_displayed(player):
        return player.round_number == 1

class GetMoneyNoworFuture(Page):
    form_model = 'player'
    form_fields = ['get_money_now_or_future', 'num_listen_times', 'decision_duration']

    @staticmethod
    def is_displayed(player):
        return True

    @staticmethod
    def vars_for_template(player):
        setup_questionaire_parameters_pairs(player)
        # 保持每個受試者從頭到尾的treatment都一樣，第二輪以後的treatment都從前一回取出
        if player.round_number >= 2:
            previous = player.in_round(player.round_number - 1)
            player.treatment_words = previous.treatment_words
            player.treatment_number = previous.treatment_number

        # 最後一回時，選出要實現的報酬
        if player.round_number == C.NUM_ROUNDS:
            select_questionaire(player)

        # 顯示 week 或 weeks
        if player.waiting_period == 1:
            display = 'week'
        else:
            display = 'weeks'

        return {
            "treatment_words": player.treatment_words,
            "waiting_period": player.waiting_period,
            "gained_amount": player.gained_amount,
            "audio": '{}_{}_{}.m4a'.format(player.gained_amount, player.waiting_period, player.treatment_number),
            "display": display
	    }

class Survey(Page):
    form_model = 'player'
    form_fields = ['gender','bloodgroup','taiwanese','econ_manage','class_num','grade','guess']
    @staticmethod
    def is_displayed(player):
        return player.round_number == C.NUM_ROUNDS

class Results(Page):
    @staticmethod
    def is_displayed(player):
        return player.round_number == C.NUM_ROUNDS
    def vars_for_template(player):
        return player.participant.vars['selected_questionaire']

class PayoffInformation(Page):
    form_model = 'player'
    form_fields = ['account']
    @staticmethod
    def is_displayed(player):
        return player.round_number == C.NUM_ROUNDS

class Finish(Page):
    @staticmethod
    def is_displayed(player):
        return player.round_number == C.NUM_ROUNDS


page_sequence = [Intro1, Intro2, Intro3, Intro4, Intro5, GetMoneyNoworFuture, Survey, Results, PayoffInformation, Finish]