from otree.api import *
import random
from random import randint
import json


doc = """
Original experiment
"""


class C(BaseConstants):
    NAME_IN_URL = 'original_exp'
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
    treatment_speed = models.FloatField(initial = 0) # treatment
    get_money_now_or_future = models.StringField(label = '請選擇您要今天或未來的報酬', widget = widgets.RadioSelect, choices = [['now', '選擇今天的報酬'], ['future','選擇未來的報酬']])
    get_money_now_or_future_test = models.StringField(label = '請選擇您要今天或未來的報酬', widget = widgets.RadioSelect, choices = [['now', '選擇今天的報酬'], ['future','選擇未來的報酬']]) # 因為是範例，所以作答結果不記在記錄正式實驗的field

    num_listen_times = models.IntegerField(initial = 0) # 聽了幾次，單位為次數 (hidden，根據使用者行為紀錄)
    decision_duration = models.FloatField(initial = 0) # 決策時長，單位為秒數 (hidden，根據使用者行為紀錄)
    is_selected = models.BooleanField(initial = False) # 是否為最後電腦選中的 round (hidden，最後一回合會抽出並寫入)
   
    # Payoff account
    account = models.StringField(label = "請填入您的帳號資料")

    # Survey
    gender = models.StringField(label = "1. 您的性別是？", widget = widgets.RadioSelect, choices = ["男", "女", "不指定"])
    bloodgroup = models.StringField(label = "2. 您的血型是？", widget = widgets.RadioSelect, choices = ["A型", "B型", "AB型", "O型", "未知", "以上皆非"])
    taiwanese = models.StringField(label = "3. 您是否為台灣本地生？", widget = widgets.RadioSelect, choices = ["台灣本地生", "非台灣本地生(例如僑生、外籍交換生學生))"])
    econ_manage = models.StringField(label = "4. 您是否是經濟系或管理學院的學生？", widget = widgets.RadioSelect, choices = ["是", "否"])
    class_num = models.StringField(label = "5. 您修過多少門經濟學的課程？", widget = widgets.RadioSelect, choices = ["0門", "1門", "2門", "3門", "4門", "5門", "超過5門"])
    grade = models.StringField(label = "6. 您的系級是？", widget = widgets.RadioSelect, choices = ["大學部1年級", "大學部2年級", "大學部3年級", "大學部4年級", "大學部5年級以上", "碩士班學生"])
    guess = models.LongStringField(label = "7. 請您猜測本實驗的目的為何?", blank=True)


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

    available_speed_list = [0.7, 0.8, 0.9]
    speed_list = []

    def prepare_list(all_players): # 事先準備好所有受試者的treatment
        Treatment.speed_list.clear()
        Treatment.prepare_participant_ids_if_needed(all_players)
        count = int(len(Treatment.participant_ids) / len(Treatment.available_speed_list)) # 例如有5人，平均分配兩組 treatment，那就是 5/2 = 2（不取餘數）
        for each_option in Treatment.available_speed_list:
            for i in range(count):
                Treatment.speed_list.append(each_option)
        while len(Treatment.speed_list) < len(Treatment.participant_ids): # 若因前面 for 迴圈中不能整除，也就是 `speech_speed_list` 不能完平均地分配給所有 participants，則最後會不夠，在此補上。（如果 `speed_available_list` 就兩個，那最多就差1，也就是最多會差到(count - 1)個）
            Treatment.speed_list.append(random.choice(Treatment.available_speed_list)) # 剩下的就隨機挑選
        random.shuffle(Treatment.speed_list) # 打亂原有 list 順序


# FUNCTIONS
def creating_session(subsession):
    if subsession.round_number == 1:
        Treatment.prepare_participant_ids_if_needed(subsession.get_players())
        Treatment.prepare_list(subsession.get_players())
        for player in subsession.get_players():
            participant = player.participant
            pid = participant.id_in_session - 1
            player.treatment_speed = Treatment.speed_list[pid]

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
    form_fields = ['treatment_speed', 'get_money_now_or_future_test']

    @staticmethod
    def vars_for_template(player):
        return {
            "treatment_speed": player.treatment_speed
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

    def is_displayed(player):
        return True

    @staticmethod
    def vars_for_template(player):
        setup_questionaire_parameters_pairs(player)
        # 保持每個受試者從頭到尾的treatment都一樣，第二輪以後的treatment都從前一回取出
        if player.round_number >= 2:
            previous = player.in_round(player.round_number - 1)
            player.treatment_speed = previous.treatment_speed
        # 最後一回時，選出要實現的報酬
        if player.round_number == C.NUM_ROUNDS:
            select_questionaire(player)
        return {
            "treatment_speed": player.treatment_speed,
            "waiting_period": player.waiting_period,
            "gained_amount": player.gained_amount
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