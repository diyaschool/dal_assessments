import textwrap
from os import listdir
from os.path import isfile, join
import threading
import telebot
import requests
import json
import shutil
import datetime
import ast
import user_manager
import hashlib
import sheets_api
import flask
import time
import os
import string
import random
import uuid
import ipaddress
from dateutil import tz
import hmac
from collections import OrderedDict

#################### Initialize ####################

app = flask.Flask(__name__, static_url_path='/')

with open('../data/telebot_key') as f:
    tg_secret_key = hashlib.sha256(f.read().strip().encode()).digest()

with open('../data/telebot_key') as f:
    bot = telebot.TeleBot(f.read().strip(), parse_mode='Markdown')

tg_bot_username = bot.get_me().username

try:
    with open('../data/cookie_key') as f:
        fdata = f.read()
    app.secret_key = fdata
except:
    key = uuid.uuid4().hex
    app.secret_key = key
    with open('../data/cookie_key', 'w') as f:
        f.write(key)

with open('../data/auth_domains') as f:
    DOMAINS = f.read().split('\n')
DOMAIN = DOMAINS[0]

anonymous_urls = ['/favicon.ico', '/clear_test_cookies', '/logo.png', '/background.png', '/loading.gif', '/update_server', '/github_sign_in/signin/', '/github_logo.png', '/telegram_logo.webp', '/tg_auth/signin/']
mobile_agents = ['Android', 'iPhone', 'iPod touch']

user_credentials = {}

from_zone = tz.tzlocal()
to_zone = tz.gettz('Asia/Kolkata')

#################### Utility Functions ####################

def send_telegram_message(username, text, type, notification=True):
    with open('../data/tg_bot_settings/'+username) as f:
        tg_settings = parse_dict(f.read())
    if tg_settings.get(type) != True:
        return False
    try:
        with open('../data/telegram_username_credentials/'+username) as f:
            user_id = f.read()
    except FileNotFoundError:
        return False
    try:
        bot.send_message(user_id, text, disable_notification=not notification)
        return True
    except:
        return False

def get_data_check_string(data):
    data = OrderedDict(sorted(data.items()))
    data_check_string = '\n'.join(['%s=%s' % (key, value) for (key, value) in data.items() if key != 'hash'])
    return data_check_string

def check_telegram_auth_data(dict_data):
    data_check_string = get_data_check_string(dict_data)
    signature = hmac.new(tg_secret_key, msg=data_check_string.encode(), digestmod=hashlib.sha256).hexdigest()
    verified = False
    if hmac.compare_digest(dict_data.get('hash'), signature):
        if int(time.time()) - int(dict_data.get('auth_date')) < 86400:
            verified = True
        else:
            return 'The session has expired, please try again.'
    else:
        return ''
    return verified

def get_github_profile(access_token):
    req = requests.get('https://api.github.com/user', headers={'Authorization': f'token {access_token}'})
    return req.json()

def parse_access_token_str(token_str):
    if token_str[:5] == 'error':
        return False
    vars = str(token_str).split('&')
    access_token = vars[0].split('=')[1]
    return access_token

def get_github_access_token(code):
    with open('../data/github_credentials.json') as f:
        data = json.loads(f.read())
    client_id = data['client_id']
    client_secret = data['client_secret']
    req = requests.post(f"https://github.com/login/oauth/access_token?client_id={client_id}&redirect_uri={flask.request.url_root+'github_sign_in/'}&client_secret={client_secret}&code={code}")
    access_token = parse_access_token_str(req.text)
    if access_token == False:
        return False
    return access_token

def parse_dict(str_data):
    try:
        return json.loads(str_data)
    except json.decoder.JSONDecodeError:
        return ast.literal_eval(str_data)

def check_sharing_perms(test_metadata, username):
    if test_metadata.get('sharing') == None:
        return {"edit": False, "overview-analytics": False, "individual-analytics": False, "files": False, "attend": False}
    for user in test_metadata['sharing']:
        if user['username'] == username:
            return user['settings']
    return {"edit": False, "overview-analytics": False, "individual-analytics": False, "files": False, "attend": False}

def check_hook_integrity(ip):
    if ipaddress.ip_address(ip) in ipaddress.ip_network('192.30.252.0/22') or ipaddress.ip_address(ip) in ipaddress.ip_network('185.199.108.0/22') or ipaddress.ip_address(ip) in ipaddress.ip_network('140.82.112.0/20'):
        return True
    else:
        return False

def get_user_response(username, test_id):
    try:
        with open('../data/response_data/'+test_id+'.json') as f:
            data = parse_dict(f.read())
    except FileNotFoundError:
        return False
    for i, response in enumerate(data['responses']):
        if response['username'] == username:
            return str(i)
    return False

def save_test_response(username, test_id):
    user_data = get_user_data(username)
    with open('../data/user_data/'+username+'/test_data/'+test_id+'.json') as f:
        tdata = parse_dict(f.read())
    tdata['completed'] = True
    with open('../data/user_data/'+username+'/test_data/'+test_id+'.json', 'w') as f:
        f.write(json.dumps(tdata))
    total_time = 0
    times = []
    for i in tdata['question_stream']:
        total_time += i['time_taken']
        times.append(i['time_taken'])
    data = {}
    data['total_time'] = int(total_time)
    data['score'] = tdata['score']
    data['username'] = username
    user_data = get_user_data(username)
    data['name'] = user_data['name']
    data['average_time'] = round(sum(times)/len(times), 2)
    with open('../data/user_data/'+username+'/test_data/'+test_id+'.json') as f:
        data['question_stream'] = parse_dict(f.read())['question_stream']
    now = datetime.datetime.now()
    now.replace(tzinfo=from_zone)
    now = now.astimezone(to_zone)
    if now.hour > 12:
        c_m = 'PM'
        hour = now.hour-12
    else:
        c_m = 'AM'
        hour = now.hour
    if now.hour == 12:
        c_m = 'PM'
        hour = hour
    if len(str(now.minute)) == 1:
        minute = '0'+str(now.minute)
    else:
        minute = now.minute
    with open('../data/test_metadata/'+test_id+'.json') as f:
        test_metadata = parse_dict(f.read())
    data["time_stamp"] = str(hour)+":"+str(minute)+":"+str(now.second)+' '+c_m
    data["long_time_stamp"] = str(now.day)+"-"+str(now.month)+"-"+str(now.year)+" "+str(hour)+":"+str(minute)+":"+str(now.second)+' '+c_m
    response_id = get_user_response(username, test_id)
    if response_id != False:
        with open('../data/response_data/'+test_id+'.json') as f:
            cdata = parse_dict(f.read())
        cresponse_count = len(cdata['responses'])
        data['index'] = int(response_id)+1
        try:
            data['attempts'] = cdata['responses'][int(response_id)]['attempts'] + 1
        except KeyError:
            data['attempts'] = 2
        cdata['responses'][int(response_id)] = data
        with open('../data/response_data/'+test_id+'.json', 'w') as f:
            f.write(json.dumps(cdata))
    else:
        try:
            with open('../data/response_data/'+test_id+'.json') as f:
                cdata = parse_dict(f.read())
            cresponse_count = len(cdata['responses'])
            with open('../data/user_data/'+test_metadata['owner']+'/created_tests/'+test_id+'.json') as f:
                cr_fdata = parse_dict(f.read())
            cr_fdata['responses_count'] = len(cdata['responses'])+1
            with open('../data/user_data/'+test_metadata['owner']+'/created_tests/'+test_id+'.json', 'w') as f:
                f.write(json.dumps(cr_fdata))
            data['index'] = cresponse_count+1
            data['attempts'] = 1
            cdata['responses'].append(data)
            with open('../data/response_data/'+test_id+'.json', 'w') as f:
                f.write(json.dumps(cdata))
        except FileNotFoundError:
            with open('../data/user_data/'+test_metadata['owner']+'/created_tests/'+test_id+'.json') as f:
                cr_fdata = parse_dict(f.read())
            cr_fdata['responses_count'] = 1
            with open('../data/user_data/'+test_metadata['owner']+'/created_tests/'+test_id+'.json', 'w') as f:
                f.write(json.dumps(cr_fdata))
            cdata = {}
            cdata['responses'] = []
            data['index'] = 1
            data['attempts'] = 1
            cdata['responses'].append(data)
            with open('../data/response_data/'+test_id+'.json', 'w') as f:
                f.write(json.dumps(cdata))

def delete_score(username, test_id):
    try:
        os.remove('../data/user_data/'+username+'/test_data/'+test_id+'.json')
    except FileNotFoundError:
        pass

def update_score(username, test_id, ans_res, difficulty, question_id, answer_index, score, ans_score, time_taken):
    try:
        with open('../data/user_data/'+username+'/test_data/'+test_id+'.json') as f:
            fdata = f.read()
        data = parse_dict(fdata)
        try:
            if data['completed'] == True:
                data = {}
        except KeyError:
            pass
    except FileNotFoundError:
        data = {}
    test_data = load_questions(test_id)
    if test_data == False:
        return False
    if difficulty == 0:
        difficulty = 'easy'
    elif difficulty == 1:
        difficulty = 'medium'
    elif difficulty == 2:
        difficulty = 'hard'
    if isinstance(answer_index, str):
        answer_index = -1
        ans_given_text = 'Skipped'
    else:
        ans_given_text = test_data['questions'][difficulty][question_id]['answers'][answer_index]
    now = datetime.datetime.now()
    now.replace(tzinfo=from_zone)
    now = now.astimezone(to_zone)
    if now.hour >= 12:
        c_m = 'PM'
        hour = now.hour-12
    else:
        c_m = 'AM'
        hour = now.hour
    if len(str(now.minute)) == 1:
        minute = '0'+str(now.minute)
    else:
        minute = now.minute
    try:
        data['question_stream'].append({"difficulty": difficulty, "question_id": question_id, "question": test_data['questions'][difficulty][question_id]['question'], "given_answer": ans_given_text, "given_answer_index": answer_index, 'ans_res': ans_res, 'ans_score': ans_score, "time_taken": time_taken, "time_stamp": str(hour)+":"+str(minute)+":"+str(now.second)+' '+c_m, "long_time_stamp": str(now.day)+"-"+str(now.month)+"-"+str(now.year)+" "+str(hour)+":"+str(minute)+":"+str(now.second)+' '+c_m, "index": len(data['question_stream'])+1})
    except KeyError:
        data['question_stream'] = []
        data['question_stream'].append({"difficulty": difficulty, "question_id": question_id, "question": test_data['questions'][difficulty][question_id]['question'], "given_answer": ans_given_text, "given_answer_index": answer_index, 'ans_res': ans_res, 'ans_score': ans_score, "time_taken": time_taken, "time_stamp": str(hour)+":"+str(minute)+":"+str(now.second)+' '+c_m, "long_time_stamp": str(now.day)+"-"+str(now.month)+"-"+str(now.year)+" "+str(hour)+":"+str(minute)+":"+str(now.second)+' '+c_m, "index": 1})
    data['score'] = score
    with open('../data/user_data/'+username+'/test_data/'+test_id+'.json', 'w') as f:
        f.write(json.dumps(data))
    return True

def get_user_data(user_id):
    try:
        with open('../data/user_metadata/'+user_id) as f:
            fdata = f.read()
        data = parse_dict(fdata)
        return data
    except FileNotFoundError:
        return False

def row_to_column(sheet):
    output = []
    row_len = 14
    for _ in range(row_len):
        output.append([])
    for i in range(row_len):
        for o in range(len(sheet)):
            try:
                c_cell = sheet[o][i]
            except IndexError:
                c_cell = ''
            output[i].append(c_cell)
    return output

def convert(sheet):
    try:
        sheet = sheet[1:]
        sheet = row_to_column(sheet)
        output = {}
        output['test_name'] = sheet[0][0]
        output['subject'] = sheet[0][1]
        output['tags'] = sheet[1]
        for i, tag in enumerate(output['tags']):
            if tag == '':
                output['tags'].pop(i)
        output['questions'] = {"easy": [], "medium": [], "hard": []}
        for i in range(len(sheet[2])):
            if sheet[2][i] == '':
                continue
            c_a_i = parse_dict(sheet[4][i])-1
            if sheet[5][i] == '':
                output['questions']['easy'].append({"question": sheet[2][i], "answers": sheet[3][i].split('\n'), "correct_answer_index": c_a_i})
            else:
                output['questions']['easy'].append({"question": sheet[2][i], "answers": sheet[3][i].split('\n'), "correct_answer_index": c_a_i, "image": sheet[5][i]})
        for i in range(len(sheet[6])):
            if sheet[6][i] == '':
                continue
            c_a_i = parse_dict(sheet[8][i])-1
            if sheet[9][i] == '':
                output['questions']['medium'].append({"question": sheet[6][i], "answers": sheet[7][i].split('\n'), "correct_answer_index": c_a_i})
            else:
                output['questions']['medium'].append({"question": sheet[6][i], "answers": sheet[7][i].split('\n'), "correct_answer_index": c_a_i, "image": sheet[9][i]})
        for i in range(len(sheet[10])):
            if sheet[10][i] == '':
                continue
            c_a_i = parse_dict(sheet[12][i])-1
            try:
                if sheet[13][i] == '':
                    output['questions']['hard'].append({"question": sheet[10][i], "answers": sheet[11][i].split('\n'), "correct_answer_index": c_a_i})
                else:
                    output['questions']['hard'].append({"question": sheet[10][i], "answers": sheet[11][i].split('\n'), "correct_answer_index": c_a_i, "image": sheet[13][i]})
            except IndexError:
                output['questions']['hard'].append({"question": sheet[10][i], "answers": sheet[11][i].split('\n'), "correct_answer_index": c_a_i})
        try:
            if sheet[0][2] == '':
                q_n = 0
                for difficulty in output['questions']:
                    for _ in output['questions'][difficulty]:
                        q_n += 1
                output['question_count'] = q_n
            else:
                output['question_count'] = parse_dict(sheet[0][2])
        except:
            q_n = 0
            for difficulty in output['questions']:
                for _ in output['questions'][difficulty]:
                    q_n += 1
            output['question_count'] = q_n
        return output
    except:
        return 'ERROR'

def create_new_test_sheet(owner, creds):
    dt = datetime.datetime.now()
    dt.replace(tzinfo=from_zone)
    dt = dt.astimezone(to_zone)
    c_time = str(dt.hour)+':'+str(dt.minute)+':'+str(dt.second)
    c_date = str(dt.year)+'-'+str(dt.month)+'-'+str(dt.day)
    test_list = [f for f in os.listdir('../data/test_data') if os.path.isdir(os.path.join('../data/test_data', f))]
    while 1:
        r_id = id_generator()
        if r_id in test_list:
            pass
        else:
            break
    test_id = r_id
    sheet_id = sheets_api.create_sheet(test_id, creds)
    os.mkdir('../data/test_data/'+test_id)
    os.mkdir('../data/test_data/'+test_id+'/files')
    with open('../data/test_data/'+test_id+'/config.json', 'w') as f:
        f.write('')
    with open('../data/test_metadata/'+test_id+'.json', 'w') as f:
        f.write(json.dumps({"owner": owner, "time": c_time, "date": c_date, "sheet_id": sheet_id, "last_time": c_time, "last_date": c_date}))
    with open('../data/user_data/'+owner+'/created_tests/'+test_id+'.json', 'w') as f:
        f.write(json.dumps({"last_time": c_time, "last_date": c_date, "name": "Undefined", "subject": "Undefined", "responses_count": 0}))
    return (test_id, sheet_id)

def validate_test_data(data_string):
    try:
        data = parse_dict(data_string)
    except:
        return 'SYNTAX_INVALID'
    if not isinstance(data['test_name'], str):
        if len(data['test_name']) > 30:
            return 'TEST_NAME_TOO_LONG'
        return 'TEST_NAME_INVALID'
    if not isinstance(data['subject'], str):
        if len(data['subject']) > 20:
            return 'SUBJECT_TOO_LONG'
        return 'SUBJECT_INVALID'
    if not isinstance(data['tags'], list):
        return 'TAGS_INVALID'
    if not isinstance(data['questions'], dict):
        return 'QUESTIONS_INAVLID'
    for question in data['questions']['easy']:
        if not isinstance(question['question'], str):
            if len(question['question']) > 100:
                return 'EASY_QUESTION_TOO_LONG'
            return 'EASY_QUESTION_TEXT_INVALID'
        try:
            for answer in question['answers']:
                if not isinstance(answer, str):
                    if len(answer) > 100:
                        return 'EASY_QUESTION_TOO_LONG'
                    return 'EASY_QUESTION_ANSWER_INVALID'
        except:
            return 'EASY_QUESTION_ANSWERS_INVALID'
        if not isinstance(question['correct_answer_index'], int):
            return 'EASY_CORRECT_ANSWER_INDEX_INVALID'
        try:
            question['answers'][question['correct_answer_index']]
        except:
            return 'EASY_CORRECT_ANSWER_INDEX_OUTBOUND'
        try:
            if not isinstance(question['image'], str):
                url_root = flask.request.url_root
                if question['image'][:len(url_root)] != url_root:
                    return "EASY_IMAGE_URL_SOURCE_IS_EXTERNAL"
                return 'EASY_IMAGE_URL_INVALID'
        except KeyError:
            pass
    for question in data['questions']['medium']:
        if not isinstance(question['question'], str):
            if len(question['question']) > 100:
                return 'MEDIUM_QUESTION_TOO_LONG'
            return 'MEDIUM_QUESTION_TEXT_INVALID'
        try:
            for answer in question['answers']:
                if not isinstance(answer, str):
                    if len(answer) > 100:
                        return 'MEDIUM_QUESTION_TOO_LONG'
                    return 'MEDIUM_QUESTION_ANSWER_INVALID'
        except:
            return 'MEDIUM_QUESTION_ANSWERS_INVALID'
        if not isinstance(question['correct_answer_index'], int):
            return 'MEDIUM_CORRECT_ANSWER_INDEX_INVALID'
        try:
            question['answers'][question['correct_answer_index']]
        except:
            return 'MEDIUM_CORRECT_ANSWER_INDEX_OUTBOUND'
        try:
            if not isinstance(question['image'], str):
                if question['image'][:len(url_root)] != url_root:
                    return "MEDIUM_IMAGE_URL_SOURCE_IS_EXTERNAL"
                return 'MEDIUM_IMAGE_URL_INVALID'
        except KeyError:
            pass
    for question in data['questions']['hard']:
        if not isinstance(question['question'], str):
            if len(question['question']) > 100:
                return 'HARD_QUESTION_TOO_LONG'
            return 'HARD_QUESTION_TEXT_INVALID'
        try:
            for answer in question['answers']:
                if not isinstance(answer, str):
                    if len(answer) > 100:
                        return 'HARD_QUESTION_TOO_LONG'
                    return 'HARD_QUESTION_ANSWER_INVALID'
        except:
            return 'HARD_QUESTION_ANSWERS_INVALID'
        if not isinstance(question['correct_answer_index'], int):
            return 'HARD_CORRECT_ANSWER_INDEX_INVALID'
        try:
            question['answers'][question['correct_answer_index']]
        except:
            return 'HARD_CORRECT_ANSWER_INDEX_OUTBOUND'
        try:
            if not isinstance(question['image'], str):
                if question['image'][:len(url_root)] != url_root:
                    return "HARD_IMAGE_URL_SOURCE_IS_EXTERNAL"
                return 'HARD_IMAGE_URL_INVALID'
        except KeyError:
            pass
    return True

def id_generator(size=10, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))

def load_questions(test_id):
    try:
        with open('../data/test_data/'+test_id+'/config.json') as f:
            fdata = f.read()
    except FileNotFoundError:
        return False
    try:
        data = parse_dict(fdata)
    except SyntaxError:
        return 'syntax'
    counter = 0
    for q in data["questions"]['easy']:
        if q['question'].strip() == '':
            data['questions']['easy'].pop(counter)
        counter += 1
    counter = 0
    for q in data["questions"]['medium']:
        if q['question'].strip() == '':
            data['questions']['medium'].pop(counter)
        counter += 1
    counter = 0
    for q in data["questions"]['hard']:
        if q['question'].strip() == '':
            data['questions']['hard'].pop(counter)
        counter += 1
    for j, q in enumerate(data['questions']['easy']):
        for i, ans in enumerate(q['answers']):
            if ans.strip() == '':
                data['questions']['easy'][j]['answers'].pop(i)
    for j, q in enumerate(data['questions']['medium']):
        for i, ans in enumerate(q['answers']):
            if ans.strip() == '':
                data['questions']['medium'][j]['answers'].pop(i)
    for j, q in enumerate(data['questions']['hard']):
        for i, ans in enumerate(q['answers']):
            if ans.strip() == '':
                data['questions']['hard'][j]['answers'].pop(i)
    counter = 0
    for q in data["questions"]['easy']:
        q['id'] = counter
        counter += 1
    counter = 0
    for q in data["questions"]['medium']:
        q['id'] = counter
        counter += 1
    counter = 0
    for q in data["questions"]['hard']:
        q['id'] = counter
        counter += 1
    try:
        data['question_count']
    except KeyError:
        q_n = 0
        for difficulty in data['questions']:
            for q in data['questions'][difficulty]:
                q_n += 1
        data['question_count'] = q_n
    return data

def get_difficulty(difficulty, completed_questions, questions, prev_q_res):
    if prev_q_res == True:
        if difficulty == 1:
            if len(completed_questions[2]) != len(questions['hard']):
                difficulty = 2
            elif len(completed_questions[1]) != len(questions['medium']):
                difficulty = 1
            elif len(completed_questions[0]) != len(questions['easy']):
                difficulty = 0
            else:
                return 'TEST_COMPLETE'
        elif difficulty == 2:
            if len(completed_questions[2]) != len(questions['hard']):
                difficulty = 2
            elif len(completed_questions[1]) != len(questions['medium']):
                difficulty = 1
            elif len(completed_questions[0]) != len(questions['easy']):
                difficulty = 0
            else:
                return 'TEST_COMPLETE'
        elif difficulty == 0:
            if len(completed_questions[1]) != len(questions['medium']):
                difficulty = 1
            elif len(completed_questions[2]) != len(questions['hard']):
                difficulty = 2
            elif len(completed_questions[0]) != len(questions['easy']):
                difficulty = 0
        else:
            return 'ERROR'
    elif prev_q_res == False:
        if difficulty == 2:
            if len(completed_questions[1]) != len(questions['medium']):
                difficulty = 1
            elif len(completed_questions[0]) != len(questions['easy']):
                difficulty = 0
            elif len(completed_questions[2]) != len(questions['hard']):
                difficulty = 2
            else:
                return 'TEST_COMPLETE'
        elif difficulty == 1:
            if len(completed_questions[0]) != len(questions['easy']):
                difficulty = 0
            elif len(completed_questions[1]) != len(questions['medium']):
                difficulty = 1
            elif len(completed_questions[2]) != len(questions['hard']):
                difficulty = 2
            else:
                return 'TEST_COMPLETE'
        elif difficulty == 0:
            if len(completed_questions[0]) != len(questions['easy']):
                difficulty = 0
            elif len(completed_questions[1]) != len(questions['medium']):
                difficulty = 1
            elif len(completed_questions[2]) != len(questions['hard']):
                difficulty = 2
            else:
                return 'TEST_COMPLETE'
    return difficulty

def get_question(completed_questions, questions):
    if len(completed_questions) == len(questions):
        return 'QUESTIONS_COMPLETED'
    while 1:
        q = random.choice(questions)
        if q['id'] in completed_questions:
            pass
        else:
            break
    return q

def get_created_tests_list(username):
    created_test_list = [f for f in os.listdir('../data/user_data/'+username+'/created_tests') if os.path.isfile(os.path.join('../data/user_data/'+username+'/created_tests', f))]
    created_tests = []
    for test in created_test_list:
        with open('../data/user_data/'+username+'/created_tests/'+test) as f:
            created_tests.append(parse_dict(f.read()))
    sort_prep_list = []
    for i, test in enumerate(created_tests):
        test['id'] = created_test_list[i][:-5]
        temp_id = id_generator(5)
        sort_prep_list.append(test['last_date']+' '+test['last_time']+' '+temp_id)
        test['temp_id'] = temp_id
    sorted_prep_list = sorted(sort_prep_list)
    final_sorted_list = []
    for test_sort_id in sorted_prep_list:
        test_sort_id = test_sort_id[-5:]
        for test in created_tests:
            if test['temp_id'] == test_sort_id:
                break
        final_sorted_list.append(test)
    for test in final_sorted_list:
        test.pop('temp_id')
    final_sorted_list.reverse()
    return final_sorted_list

#################### Reqeust Handlers ####################

@app.before_request
def before_request():
    if flask.request.headers['Host'] not in DOMAINS:
        return flask.redirect('http://'+DOMAIN+flask.request.path, 301)
    onlyfiles = [f for f in listdir('static/') if isfile(join('static/', f))]
    if flask.request.path != '/login' and flask.request.path not in anonymous_urls and flask.request.path.strip("/") not in onlyfiles:
        try:
            username = flask.session['username']
            f = open('../data/user_metadata/'+username)
            f.close()
            if flask.session['perm_auth_key'] != hashlib.sha256(get_user_data(username)['password'].encode()).hexdigest():
                flask.session['login_ref'] = flask.request.path
                return flask.redirect('/login')
        except KeyError:
            flask.session['login_ref'] = flask.request.path
            return flask.redirect('/login')
        except FileNotFoundError:
            flask.session['login_ref'] = flask.request.path
            return flask.redirect('/login')
        user_data = get_user_data(flask.session['username'])
        if user_data.get('has_changed_password') != None:
            if flask.request.path != '/change_password' and flask.request.path != '/logout':
                return flask.redirect('/change_password')

@app.after_request
def after_request(response):
    response.headers["Server"] = "DAL-Server/0.9"
    response.headers["Developers"] = "Chaitanya, Harsha, Kushal, Piyush"
    response.headers["Origin-School"] = "Diya Academy of Learning"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

@app.context_processor
def context_processor():
    def url_root():
        return flask.request.url_root
    return dict(url_root=url_root)

#################### Content Endpoints ####################

@app.route('/')
def home():
    desktop = True
    for agent in mobile_agents:
        if agent in flask.request.headers['User-Agent']:
            desktop = False
    user_data = get_user_data(flask.session['username'])
    created_tests = get_created_tests_list(flask.session['username'])
    if desktop:
        return flask.render_template('home.html', username=flask.session['username'], name=user_data['name'], created_tests=created_tests, c_test_len=len(created_tests))
    else:
        return flask.render_template('mobile/home.html', username=flask.session['username'], name=user_data['name'])

@app.route('/logout')
def logout():
    flask.session.pop('username')
    return flask.redirect('/login')

@app.route('/clear_test_cookies')
def clear_test_cookies():
    try:
        href = flask.session['error_referrer']
    except KeyError:
        href = '/'
    try:
        flask.session.pop('t')
    except KeyError:
        pass
    return flask.render_template('cookie_cleared.html', href=href)

@app.route('/t/<code>/verify', methods=['POST'])
def t_verify(code):
    data = flask.request.form
    if str(data['answer']) == str(flask.session['t']['c_a_i']):
        flask.session['t']['prev_q_res'] = True
    else:
        flask.session['t']['prev_q_res'] = False
    if flask.session['t']['prev_q_res'] == True:
        if flask.session['t']['difficulty'] == 0:
            ans_score = 10
        elif flask.session['t']['difficulty'] == 1:
            ans_score = 15
        elif flask.session['t']['difficulty'] == 2:
            ans_score = 20
        flask.session['t']['score'] = str(parse_dict(flask.session['t']['score'])+ans_score)
    else:
        ans_score = 0
    flask.session['t']['verified'] = True
    time_taken = time.time()-flask.session['t']['time']
    update_score(flask.session['username'], code, flask.session['t']['prev_q_res'], flask.session['t']['difficulty'], flask.session['t']['q_id'], parse_dict(data['answer']), flask.session['t']['score'], ans_score, time_taken)
    flask.session['t']['q'] = str(parse_dict(flask.session['t']['q'])+1)
    flask.session.modified = True
    return flask.redirect('/t/'+code)

@app.route('/t/<code>/')
def t_view(code):
    desktop = True
    for agent in mobile_agents:
        if agent in flask.request.headers['User-Agent']:
            desktop = False
    user_data = get_user_data(flask.session['username'])
    question_data = load_questions(code)
    authorized = False
    if question_data == False:
        return flask.render_template('404.html'), 404
    if question_data == 'syntax':
        return "The test was not properly created. Please contact the owner of this test."
    if 'all' in question_data['tags']:
        authorized = True
    for tag in user_data['tags']:
        if tag in question_data['tags'] or tag == 'admin' or tag == 'teacher' or tag == 'team':
            authorized = True
            break
    with open('../data/test_metadata/'+code+'.json') as f:
        test_metadata = parse_dict(f.read())
    if check_sharing_perms(test_metadata, flask.session['username'])['attend'] == True:
        authorized = True
    if authorized == False:
        return flask.render_template('401.html'), 401
    try:
        if flask.session['t']['code'] != code:
            flask.session.pop('t')
            flask.session['t'] = {}
            flask.session['t']['code'] = code
            flask.session['t']['q'] = '0'
            flask.session['t']['c_q'] = [[], [], []]
            flask.session['t']['difficulty'] = 1
            flask.session['t']['score'] = '0'
            flask.session.modified = True
    except KeyError:
        flask.session['t'] = {}
        flask.session['t']['code'] = code
        flask.session['t']['q'] = '0'
        flask.session['t']['c_q'] = [[], [], []]
        flask.session['t']['difficulty'] = 1
        flask.session['t']['score'] = '0'
        flask.session.modified = True
        return flask.redirect('/t/'+code)
    if flask.request.args.get('start') == '':
        try:
            flask.session['t']['q'] = '1'
            flask.session.modified = True
        except KeyError:
            return flask.redirect('/t/'+code)
        return flask.redirect('/t/'+code)
    elif flask.request.args.get('exit') == '':
        flask.session.pop('t')
        flask.session.modified = True
        delete_score(flask.session['username'], code)
        return flask.redirect('/t/'+code)
    if len(flask.session['t']['c_q'][0]) == len(question_data['questions']['easy']) and len(flask.session['t']['c_q'][1]) == len(question_data['questions']['medium']) and len(flask.session['t']['c_q'][2]) == len(question_data['questions']['hard']):
        score = flask.session['t']['score']
        flask.session.pop('t')
        flask.session.modified = True
        save_test_response(flask.session['username'], code)
        delete_score(flask.session['username'], code)
        return flask.render_template('t_completed.html', test_name=question_data['test_name'], score=score, name=user_data['name'], username=flask.session['username'], code=code)
    else:
        if question_data['question_count'] == parse_dict(flask.session['t']['q'])-1:
            score = flask.session['t']['score']
            flask.session.pop('t')
            flask.session.modified = True
            try:
                user_data['test_data'][code] = score
            except KeyError:
                user_data['test_data'] = {}
                user_data['test_data'][code] = score
            if 'teacher' in user_data['tags'] or 'admin' in user_data['tags'] or 'team' in user_data['tags']:
                pass
            else:
                with open('../data/user_metadata/'+flask.session['username'], 'w') as f:
                    f.write(json.dumps(user_data))
            save_test_response(flask.session['username'], code)
            delete_score(flask.session['username'], code)
            return flask.render_template('t_completed.html', test_name=question_data['test_name'], score=score, name=user_data['name'], username=flask.session['username'], code=code)
    if flask.session['t']['q'] == '0':
        q_n = question_data['question_count']
        flask.session['t']['verified'] = True
        flask.session.modified = True
        if desktop:
            return flask.render_template('t0.html', code=code, data=question_data, username=flask.session['username'], name=user_data['name'], q_n=q_n, subject=question_data['subject'])
        else:
            return flask.render_template('mobile/t0.html', code=code, data=question_data, username=flask.session['username'], name=user_data['name'], q_n=q_n, subject=question_data['subject'])
    else:
        if flask.session['t']['q'] == '1':
            if flask.session['t'].get('verified') == True:
                flask.session['t']['time'] = time.time()
                question = get_question(flask.session['t']['c_q'][1], question_data['questions']['medium'])
                flask.session['t']['q_id'] = question['id']
                if question == 'QUESTIONS_COMPLETED':
                    return flask.render_template('500.html'), 500
                flask.session['t']['c_q'][1].append(question['id'])
                flask.session['t']['c_a_i'] = question['correct_answer_index']
                flask.session['t'].pop('verified')
                flask.session.modified = True
            else:
                question = question_data['questions']['medium'][flask.session['t']['q_id']]
            q_number = flask.session['t']['q']
            try:
                image_url = question['image']
            except KeyError:
                image_url = None
            height_extend = 0
            if desktop:
                if len(question['question']) >= 40:
                    temp_question = textwrap.wrap(question['question'], 50)
                    for _ in temp_question:
                        height_extend += 10
                    question['question'] = temp_question
                else:
                    question['question'] = [question['question']]
            else:
                if len(question['question']) >= 30:
                    temp_question = textwrap.wrap(question['question'], 20)
                    for _ in temp_question:
                        height_extend += 20
                    question['question'] = temp_question
                else:
                    question['question'] = [question['question']]
            o_answers = []
            counter = 0
            for answer in question['answers']:
                o_answers.append({'answer': answer, "id": str(counter)})
                counter += 1
            random.shuffle(o_answers)
            if desktop:
                return flask.render_template('t.html', code=code, question_data=question, ans_range=range(len(question['answers'])), data=question_data, q_number=q_number, image_url=image_url, username=flask.session['username'], name=user_data['name'], total_height=650+height_extend, answers=o_answers)
            else:
                return flask.render_template('mobile/t.html', code=code, question_data=question, ans_range=range(len(question['answers'])), data=question_data, q_number=q_number, image_url=image_url, username=flask.session['username'], name=user_data['name'], total_height=650+height_extend, answers=o_answers)
        else:
            try:
                if flask.session['t'].get('verified') == True:
                    prev_q_res = flask.session['t']['prev_q_res']
                    flask.session['t'].pop('prev_q_res')
                    flask.session['t']['time'] = time.time()
                    c_difficulty = get_difficulty(flask.session['t']['difficulty'], flask.session['t']['c_q'], question_data['questions'], prev_q_res)
                    flask.session['t']['difficulty'] = c_difficulty
                    if c_difficulty == 0:
                        question = get_question(flask.session['t']['c_q'][0], question_data['questions']['easy'])
                    elif c_difficulty == 1:
                        question = get_question(flask.session['t']['c_q'][1], question_data['questions']['medium'])
                    elif c_difficulty == 2:
                        question = get_question(flask.session['t']['c_q'][2], question_data['questions']['hard'])
                    flask.session['t']['q_id'] = question['id']
                    if question == 'QUESTIONS_COMPLETED':
                        return flask.render_template('500.html'), 500
                    flask.session['t']['c_q'][c_difficulty].append(question['id'])
                    q_number = flask.session['t']['q']
                    flask.session['t'].pop('verified')
                    flask.session['t']['c_a_i'] = question['correct_answer_index']
                    flask.session.modified = True
                else:
                    prev_q_res = False
                    c_difficulty = flask.session['t']['difficulty']
                    q_id = flask.session['t']['q_id']
                    if c_difficulty == 0:
                        question = question_data['questions']['easy'][q_id]
                    elif c_difficulty == 1:
                        question = question_data['questions']['medium'][q_id]
                    elif c_difficulty == 2:
                        question = question_data['questions']['hard'][q_id]
                    q_number = flask.session['t']['q']
            except KeyError:
                prev_q_res = False
                c_difficulty = flask.session['t']['difficulty']
                q_id = flask.session['t']['q_id']
                if c_difficulty == 0:
                    question = question_data['questions']['easy'][q_id]
                elif c_difficulty == 1:
                    question = question_data['questions']['medium'][q_id]
                elif c_difficulty == 2:
                    question = question_data['questions']['hard'][q_id]
                q_number = flask.session['t']['q']
            try:
                image_url = question['image']
            except KeyError:
                image_url = None
            height_extend = 0
            if desktop:
                if len(question['question']) >= 40:
                    temp_question = textwrap.wrap(question['question'], 50)
                    for _ in temp_question:
                        height_extend += 10
                    question['question'] = temp_question
                else:
                    question['question'] = [question['question']]
            else:
                if len(question['question']) >= 30:
                    temp_question = textwrap.wrap(question['question'], 20)
                    for _ in temp_question:
                        height_extend += 20
                    question['question'] = temp_question
                else:
                    question['question'] = [question['question']]
            o_answers = []
            counter = 0
            for answer in question['answers']:
                o_answers.append({'answer': answer, "id": str(counter)})
                counter += 1
            random.shuffle(o_answers)
            if desktop:
                return flask.render_template('t.html', code=code, question_data=question, ans_range=range(len(question['answers'])), data=question_data, q_number=q_number, image_url=image_url, username=flask.session['username'], name=user_data['name'], total_height=650+height_extend, answers=o_answers)
            else:
                return flask.render_template('mobile/t.html', code=code, question_data=question, ans_range=range(len(question['answers'])), data=question_data, q_number=q_number, image_url=image_url, username=flask.session['username'], name=user_data['name'], total_height=650+height_extend, answers=o_answers)

@app.route('/login', methods=['GET', 'POST'])
def login():
    desktop = True
    for agent in mobile_agents:
        if agent in flask.request.headers['User-Agent']:
            desktop = False
    if flask.request.method == 'GET':
        error = None
        try:
            error = flask.session['login_error']
            flask.session.pop('login_error')
        except KeyError:
            pass
        with open('../data/github_credentials.json') as f:
            data = json.loads(f.read())
        client_id = data['client_id']
        client_secret = data['client_secret']
        if desktop:
            return flask.render_template('login.html', error=error, username='', client_id=client_id, tg_bot_username=tg_bot_username)
        else:
            return flask.render_template('mobile/login.html', error=error, username='', tg_bot_username=tg_bot_username)
    elif flask.request.method == 'POST':
        form_data = flask.request.form
        try:
            with open('../data/user_metadata/'+form_data['username'].lower()) as f:
                fdata = f.read()
            data = parse_dict(fdata)
            password = hashlib.sha224(form_data['password'].encode()).hexdigest()
            if data['password'] != password:
                if desktop:
                    return flask.render_template('login.html', error='Invalid Credentials', username=form_data['username'], tg_bot_username=tg_bot_username)
                else:
                    return flask.render_template('mobile/login.html', error='Invalid Credentials', username=form_data['username'], tg_bot_username=tg_bot_username)
            else:
                flask.session['username'] = form_data['username'].lower()
                user_data = get_user_data(flask.session['username'])
                flask.session['perm_auth_key'] = hashlib.sha256(user_data['password'].encode()).hexdigest()
                user_data = get_user_data(flask.session['username'])
                send_telegram_message(flask.session['username'], f'Dear *{user_data["name"]}*,\nThere is a *new login* with your *password* at DAL Assessments.\n\n_If this wasn\'t you, please login quickly and change your password_', 'on_login')
                if user_data.get('has_changed_password') != None and flask.request.path != '/change_password':
                    return flask.redirect('/change_password')
                try:
                    login_ref = flask.session['login_ref']
                    flask.session.pop('login_ref')
                    return flask.redirect(login_ref)
                except KeyError:
                    return flask.redirect('/')
        except FileNotFoundError:
            if desktop:
                return flask.render_template('login.html', error='Invalid Credentials', username=form_data['username'], tg_bot_username=tg_bot_username)
            else:
                return flask.render_template('mobile/login.html', error='Invalid Credentials', username=form_data['username'], tg_bot_username=tg_bot_username)

@app.route('/new_test', methods=['GET', 'POST'])
def new_test():
    user_data = get_user_data(flask.session['username'])
    if flask.request.method == 'GET':
        return flask.render_template('new_test.html', username=flask.session['username'], name=user_data['name'])
    else:
        gauth = sheets_api.authorize()
        creds = gauth.load_credentials(flask.session['username'])
        if creds == None:
            flask.session['settings_alert'] = 'Please link your Google account before creating a test'
            return flask.redirect('/settings')
        test_data = create_new_test_sheet(flask.session['username'], creds)
        test_id, _ = test_data
        send_telegram_message(flask.session['username'], f'You have just created a new test at *DAL Assessments*. Here is the link to it: {flask.request.url_root}/t/{test_id}/edit', 'test_attend', False)
        return flask.redirect('/t/'+test_id+'/edit')

@app.route('/t/<code>/edit/', methods=['GET', 'POST', 'PUT'])
def test_edit(code):
    if '\\' in code or '.' in code:
        return flask.render_template('500.html'), 500
    user_data = get_user_data(flask.session['username'])
    try:
        with open('../data/test_metadata/'+code+'.json') as f:
            data = parse_dict(f.read())
    except:
        return flask.render_template('404.html'), 404
    if data['owner'] == flask.session['username'] or 'admin' in user_data['tags'] or 'team' in user_data['tags'] or check_sharing_perms(data, flask.session['username'])['edit'] == True:
        pass
    else:
        return flask.redirect('/t/'+code)
    with open('../data/test_data/'+code+'/config.json') as f:
        test_data = f.read()
    sheet_id = data.get('sheet_id')
    try:
        title = parse_dict(test_data)['test_name']
    except:
        title = 'Untitled'
    if flask.request.method == 'GET':
        sync_arg = flask.request.args.get('sync')
        if sync_arg == '':
            gauth = sheets_api.authorize()
            creds = gauth.load_credentials(flask.session['username'])
            if gauth.verify_token(creds) == False:
                return flask.redirect('/sheets_api_authorize')
            n_test_data = sheets_api.get_values(sheet_id, creds)
            n_test_data = convert(n_test_data)
            if n_test_data == "ERROR":
                return flask.render_template('t_edit.html', test_data=test_data, sheet_id=sheet_id, title=title, username=flask.session['username'], name=user_data['name'], code=code, alert="Error during parsing spreadsheet", base_uri=flask.request.url_root)
            test_validation = validate_test_data(str(n_test_data))
            if test_validation == True:
                with open('../data/test_data/'+code+'/config.json', 'w') as f:
                    f.write(json.dumps(n_test_data))
                with open('../data/test_metadata/'+code+'.json') as f:
                    metadata = parse_dict(f.read())
                with open('../data/test_metadata/'+code+'.json', 'w') as f:
                    dt = datetime.datetime.now()
                    dt.replace(tzinfo=from_zone)
                    dt = dt.astimezone(to_zone)
                    c_time = str(dt.hour)+':'+str(dt.minute)+':'+str(dt.second)
                    c_date = str(dt.year)+'-'+str(dt.month)+'-'+str(dt.day)
                    metadata['last_time'] = c_time
                    metadata['last_date'] = c_date
                    f.write(json.dumps(metadata))
                try:
                    with open('../data/user_data/'+flask.session['username']+'/created_tests/'+code+'.json') as f:
                        cr_fdata = parse_dict(f.read())
                    try:
                        with open('../data/response_data/'+code+'.json') as g:
                            responses_count = len(parse_dict(g.read())['responses'])
                    except FileNotFoundError:
                        responses_count = 0
                    with open('../data/user_data/'+flask.session['username']+'/created_tests/'+code+'.json', 'w') as f:
                        cr_fdata['name'] = n_test_data['test_name']
                        cr_fdata['subject'] = n_test_data['subject']
                        cr_fdata['responses_count'] = responses_count
                        cr_fdata['last_time'] = c_time
                        cr_fdata['last_date'] = c_date
                        f.write(json.dumps(cr_fdata))
                except FileNotFoundError:
                    with open('../data/user_data/'+flask.session['username']+'/created_tests/'+code+'.json', 'w') as f:
                        f.write(json.dumps({"last_time": c_time, "last_date": c_date, "name": "Undefined", "subject": "Undefined", "responses_count": 0}))
                return flask.redirect('/t/'+code+'/edit')
            else:
                return flask.render_template('t_edit.html', test_data=test_data, sheet_id=sheet_id, title=title, username=flask.session['username'], name=user_data['name'], code=code, alert="Error: "+test_validation, base_uri=flask.request.url_root)
        else:
            return flask.render_template('t_edit.html', test_data=test_data, sheet_id=sheet_id, title=title, username=flask.session['username'], name=user_data['name'], code=code, alert=None, base_uri=flask.request.url_root)
    elif flask.request.method == 'POST':
        data = flask.request.form
        v_output = validate_test_data(data['test_data'])
        if v_output == True:
            with open('../data/test_data/'+code+'/config.json', 'w') as f:
                f.write(data['test_data'])
            return 'validated, modified config file'
        else:
            return v_output, 400
    elif flask.request.method == 'PUT':
        with open('../data/test_data/'+code+'/config.json') as f:
            fdata = f.read()
        return fdata

@app.route('/t/<code>/analytics/')
def test_analytics(code):
    user_data = get_user_data(flask.session['username'])
    try:
        with open('../data/test_metadata/'+code+'.json') as f:
            data = parse_dict(f.read())
    except:
        return flask.render_template('404.html'), 404
    if data['owner'] == flask.session['username'] or 'admin' in user_data['tags'] or 'team' in user_data['tags'] or check_sharing_perms(data, flask.session['username'])['overview-analytics'] == True:
        pass
    else:
        if 'teacher' in user_data['tags']:
            return flask.render_template('401.html'), 401
        else:
            return flask.redirect('/t/'+code)
    with open('../data/test_data/'+code+'/config.json') as f:
        test_data = f.read()
    try:
        title = parse_dict(test_data)['test_name']
    except KeyError:
        return "The test was not properly created. Please contact the owner of this test."
    except SyntaxError:
        return "The test was not properly created. Please contact the owner of this test."
    try:
        with open('../data/response_data/'+code+'.json') as f:
            response_data = parse_dict(f.read())
    except FileNotFoundError:
        response_data = {'responses': []}
    return flask.render_template('test_analytics.html', test_name=title, username=flask.session['username'], name=user_data['name'], responses=response_data['responses'], response_count=len(response_data['responses']), code=code)

@app.route('/t/<code>/analytics/<username>/')
def test_analytics_user(code, username):
    auserdata = get_user_data(username)
    user_data = get_user_data(flask.session['username'])
    try:
        with open('../data/test_metadata/'+code+'.json') as f:
            data = parse_dict(f.read())
    except:
        return flask.render_template('404.html'), 404
    if data['owner'] != flask.session['username']:
        if username != flask.session['username']:
            if check_sharing_perms(test_metadata, flask.session['username'])['individual-analytics'] != True:
                if 'teacher' in user_data['tags']:
                    return flask.render_template('401.html'), 401
                else:
                    return flask.redirect('/t/'+code)
    with open('../data/test_data/'+code+'/config.json') as f:
        test_data = f.read()
    try:
        title = parse_dict(test_data)['test_name']
    except KeyError:
        return "The test was not properly created. Please contact the owner of this test."
    except SyntaxError:
        return "The test was not properly created. Please contact the owner of this test."
    with open('../data/response_data/'+code+'.json') as f:
        fdata = parse_dict(f.read())['responses'][int(get_user_response(username, code))]
        response_data = fdata['question_stream']
        score = fdata['score']
    for response in response_data:
        response['time_taken'] = round(response['time_taken'], 2)
        if response['ans_res']:
            response['ans_res'] = 'Correct'
        else:
            response['ans_res'] = 'Wrong'
        response['difficulty'] = response['difficulty'].capitalize()
        response['full_question'] = response['question']
        if len(response['question']) > 20:
            response['question'] = response['question'][:20]+'...'
        response['full_given_answer'] = response['given_answer']
        if len(response['given_answer']) > 20:
            response['given_answer'] = response['given_answer'][:20]+'...'
    try:
        fdata['attempts']
        attempts = True
    except:
        attempts = False
    return flask.render_template('test_analytics_username.html', test_name=title, username=flask.session['username'], name=user_data['name'], responses=response_data, response_count=len(response_data), code=code, auserdata=auserdata, score=score, fdata=fdata, attempts_bool=attempts)

@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    user_data = get_user_data(flask.session['username'])
    if flask.request.method == 'GET':
        return flask.render_template('change_password.html', username=flask.session['username'], name=user_data['name'], error=None)
    elif flask.request.method == 'POST':
        data = flask.request.form
        if hashlib.sha224(data['current_password'].encode()).hexdigest() == user_data['password']:
            if data['new_password'] == data['conf_password']:
                if data['current_password'] != data['new_password']:
                    user_manager.change_password(flask.session['username'], data['new_password'])
                    flask.session['perm_auth_key'] = hashlib.sha256(hashlib.sha224(data['new_password'].encode()).hexdigest().encode()).hexdigest()
                    if user_data.get('has_changed_password') == None:
                        send_telegram_message(flask.session['username'], f'Dear {user_data["name"]},\nWe have dected a change in your password.\n\n_If this doesn\'t seem to be you, quickly contact us to recover your account._', 'on_password_change')
                    try:
                        login_ref = flask.session['login_ref']
                        flask.session.pop('login_ref')
                        return flask.redirect(login_ref)
                    except KeyError:
                        return flask.redirect('/')
                else:
                    return flask.render_template('change_password.html', username=flask.session['username'], name=user_data['name'], error='Your new password must be different from the current one')
            else:
                return flask.render_template('change_password.html', username=flask.session['username'], name=user_data['name'], error='Both passwords must match')
        else:
            return flask.render_template('change_password.html', username=flask.session['username'], name=user_data['name'], error='Password incorrect')

@app.route('/settings/', methods=['GET', 'POST'])
def settings():
    user_data = get_user_data(flask.session['username'])
    if flask.request.method == 'GET':
        alert = flask.session.get('settings_alert')
        if alert == None:
            alert = 'none'
        try:
            flask.session.pop('settings_alert')
        except KeyError:
            pass
        error = flask.session.get('settings_error')
        try:
            flask.session.pop('settings_error')
        except KeyError:
            pass
        with open('../data/github_credentials.json') as f:
            data = json.loads(f.read())
        client_id = data['client_id']
        client_secret = data['client_secret']
        github_auth = False
        google_auth = False
        telegram_auth = False
        try:
            with open('../data/github_username_credentials/'+flask.session['username']) as f:
                profile_id = f.read()
            with open('../data/github_credentials/'+profile_id) as f:
                if f.read() == flask.session['username']:
                    github_auth = True
        except FileNotFoundError:
            pass
        gauth = sheets_api.authorize()
        creds = gauth.load_credentials(flask.session['username'])
        if creds != None:
            google_auth = True
        try:
            with open('../data/telegram_username_credentials/'+flask.session['username']) as f:
                profile_id = f.read()
            with open('../data/tg_bot_settings/'+flask.session['username']) as f:
                tg_bot_settings = parse_dict(f.read())
            with open('../data/telegram_credentials/'+profile_id) as f:
                if f.read() == flask.session['username']:
                    telegram_auth = True
        except FileNotFoundError:
            pass
        return flask.render_template('settings.html', username=flask.session['username'], name=user_data['name'], error=error, alert=alert, client_id=client_id, github_auth=github_auth, google_auth=google_auth, telegram_auth=telegram_auth, tg_bot_username=tg_bot_username, tg_bot_settings=tg_bot_settings)
    elif flask.request.method == 'POST':
        data = flask.request.form
        if flask.request.args.get('change_password') == '':
            if hashlib.sha224(data['current_password'].encode()).hexdigest() == user_data['password']:
                if data['new_password'] == data['conf_password']:
                    if data['current_password'] != data['new_password']:
                        user_manager.change_password(flask.session['username'], data['new_password'])
                        flask.session['perm_auth_key'] = hashlib.sha256(hashlib.sha224(data['new_password'].encode()).hexdigest().encode()).hexdigest()
                        flask.session['settings_alert'] = 'Your password has been changed successfully'
                        send_telegram_message(flask.session['username'], f'Dear {user_data["name"]},\nWe have dected a change in your password.\n\n_If this doesn\'t seem to be you, quickly contact us to recover your account._', 'on_password_change')
                        return flask.redirect("/settings")
                    else:
                        flask.session['settings_error'] = 'Your new password must be different from the current one'
                        return flask.redirect('/settings/')
                else:
                    flask.session['settings_error'] = 'Both passwords must match'
                    return flask.redirect('/settings/')
            else:
                flask.session['settings_error'] = 'Password incorrect'
                return flask.redirect('/settings/')
        elif flask.request.args.get('tg_bot') == '':
            form_data = flask.request.form.to_dict(flat=False)
            with open('../data/tg_bot_settings/'+flask.session['username']) as f:
                fdata =  parse_dict(f.read())
            keys = list(fdata.keys())
            keys.extend(x for x in list(form_data.keys()) if x not in keys)
            for key in keys:
                try:
                    fdata[key] = bool(form_data[key][0])
                except ValueError:
                    fdata[key] = False
                except KeyError:
                    fdata[key] = False
            with open('../data/tg_bot_settings/'+flask.session['username'], 'w') as f:
                f.write(json.dumps(fdata))
            flask.session['settings_alert'] = 'Applied Telegram Assistant settings'
            return flask.redirect('/settings/')

@app.route('/sheets_api_authorize/', methods=['GET', 'POST'])
def sheets_api_authorize():
    global user_credentials
    user_data = get_user_data(flask.session['username'])
    if flask.request.method == 'GET':
        try:
            user_credentials.pop(flask.session['username'])
        except KeyError:
            pass
        gauth = sheets_api.authorize()
        creds = gauth.load_credentials(flask.session['username'])
        user_credentials[flask.session['username']] = gauth
        if creds:
            if gauth.verify_token(creds):
                flask.session['settings_alert'] = 'You have already linked your Google Account'
                return flask.redirect('/settings')
            else:
                url = gauth.get_url()
                return flask.render_template('sheets_code.html', url=url, username=flask.session['username'], name=user_data['name'])
        else:
            url = gauth.get_url()
            return flask.render_template('sheets_code.html', url=url, username=flask.session['username'], name=user_data['name'])
    else:
        data = flask.request.form
        try:
            gauth = user_credentials[flask.session['username']]
        except KeyError:
            flask.session['settings_error'] = 'Something has gone wrong...'
            return flask.redirect('/settings')
        creds = gauth.verify_code(data['code'])
        if creds != False:
            gauth.save_credentials(creds, flask.session['username'])
            user_credentials.pop(flask.session['username'])
            flask.session['settings_alert'] = 'Your Google account has successfully been linked'
            user_data = get_user_data(flask.session['username'])
            send_telegram_message(flask.session['username'], f'Hello *{user_data["name"]}*!\nYour *Google account* has successfully been *linked at DAL Assessments*. You can now freely create new tests.', 'on_linked_accounts')
            return flask.redirect('/settings')
        else:
            user_credentials.pop(flask.session['username'])
            flask.session['settings_error'] = 'There was an error during authorization'
            return flask.redirect('/settings')

@app.route('/sheets_api_authorize/delete/')
def sheets_api_authorize_delete():
    user_data = get_user_data(flask.session['username'])
    try:
        os.remove('../data/credentials/'+flask.session['username']+'.pickle')
        flask.session['settings_alert'] = 'Your Google account has been successfully unlinked'
        user_data = get_user_data(flask.session['username'])
        send_telegram_message(flask.session['username'], f'Hello *{user_data["name"]}*!\nYour *Google account* has successfully been *unlinked at DAL Assessments*. You will not be able to create new tests anymore.', 'on_linked_accounts')
        return flask.redirect('/settings')
    except FileNotFoundError:
        flask.session['settings_error'] = 'There was a problem unlinking your Google account'
        return flask.redirect('/settings')

@app.route('/upload_file')
def u_r():
    return flask.render_template('u_r.html')

@app.route('/t/<code>/upload/', methods=['GET', 'POST'])
def upload_file(code):
    if flask.request.method == 'GET':
        user_data = get_user_data(flask.session['username'])
        with open('../data/test_metadata/'+code+'.json') as f:
            test_metadata = parse_dict(f.read())
        if flask.session['username'] != test_metadata['owner']:
            if 'admin' in user_data['tags'] or 'team' in user_data['tags'] or check_sharing_perms(test_metadata, flask.session['username'])['files'] == True:
                pass
            else:
                return '<br><br><center>YOU ARE NOT AUTHORIZED TO VIEW/MODIFY FILES</center>'
        files = [f for f in os.listdir('../data/test_data/'+code+'/files') if os.path.isdir(os.path.join('../data/test_data/'+code+'/files', f))]
        all_files = {}
        for file in files:
            all_files[file] = [f for f in os.listdir('../data/test_data/'+code+'/files/'+file) if os.path.isfile(os.path.join('../data/test_data/'+code+'/files/'+file, f))][0]
        return flask.render_template('upload.html', files=all_files, base_uri=flask.request.url_root, code=code)
    elif flask.request.method == 'POST':
        f = flask.request.files['file']
        test_list = [f for f in os.listdir('../data/test_data/'+code+'/files/') if os.path.isdir(os.path.join('../data/test_data/'+code+'/files/', f))]
        while 1:
            r_id = id_generator()
            if r_id in test_list:
                pass
            else:
                break
        file_id = r_id.lower()
        os.mkdir('../data/test_data/'+code+'/files/'+file_id)
        f.save('../data/test_data/'+code+'/files/'+file_id+'/'+f.filename)
        return flask.redirect(flask.request.path)

@app.route('/github_sign_in/<loc>/')
def github_sign_in(loc):
    if loc == 'auth':
        code = flask.request.args['code']
        access_token = get_github_access_token(code)
        if access_token == False:
            flask.session['settings_error'] = 'There was an error during GitHub authentication. Please try again'
            return flask.redirect('/settings/')
        profile = get_github_profile(access_token)
        try:
            with open('../data/github_credentials/'+str(profile['id'])) as f:
                if f.read() != flask.session['username']:
                    flask.session['settings_error'] = 'This GitHub account has already been linked to another account'
                    return flask.redirect('/settings/')
                else:
                    flask.session['settings_alert'] = 'You have already linked your GitHub Account'
                    return flask.redirect('/settings/')
        except FileNotFoundError:
            pass
        with open('../data/github_credentials/'+str(profile['id']), 'w') as f:
            f.write(flask.session['username'])
        with open('../data/github_username_credentials/'+flask.session['username'], 'w') as f:
            f.write(str(profile['id']))
        flask.session['settings_alert'] = 'Your GitHub account has successfully been linked'
        user_data = get_user_data(flask.session['username'])
        send_telegram_message(flask.session['username'], f'Hello *{user_data["name"]}*!\nYour *GitHub account* has successfully been *linked at DAL Assessments*. GitHub SSO has now been enabled for your account.', 'on_linked_accounts')
        return flask.redirect('/settings/')
    elif loc == 'signin':
        code = flask.request.args['code']
        access_token = get_github_access_token(code)
        if access_token == False:
            flask.session['login_error'] = 'There was an error during GitHub authentication. Please log in with your password'
            return flask.redirect('/login')
        profile = get_github_profile(access_token)
        try:
            with open('../data/github_credentials/'+str(profile['id'])) as f:
                username = f.read()
        except FileNotFoundError:
            flask.session['login_error'] = 'You have not linked this GitHub account yet, please sign in with your password'
            return flask.redirect('/login')
        flask.session['username'] = username
        user_data = get_user_data(flask.session['username'])
        flask.session['perm_auth_key'] = hashlib.sha256(user_data['password'].encode()).hexdigest()
        send_telegram_message(flask.session['username'], f'Dear *{user_data["name"]}*,\nThere is a *new login* with your *GitHub Account* at DAL Assessments.\n\n_If this wasn\'t you, please login quickly and change your password_', 'on_linked_accounts')
        return flask.redirect('/')

@app.route('/github_auth/delete/')
def github_auth_delete():
    try:
        with open('../data/github_username_credentials/'+flask.session['username']) as f:
            profile = f.read()
        os.remove('../data/github_username_credentials/'+flask.session['username'])
        os.remove('../data/github_credentials/'+profile)
        flask.session['settings_alert'] = 'Your GitHub account has been successfully unlinked'
        user_data = get_user_data(flask.session['username'])
        send_telegram_message(flask.session['username'], f'Hello *{user_data["name"]}*!\nYour *GitHub account* has successfully been *unlinked at DAL Assessments*. Your GitHub SSO will no longer work.', 'on_linked_accounts')
        return flask.redirect('/settings')
    except FileNotFoundError:
        flask.session['settings_error'] = 'There was a problem unlinking your GitHub account'
        return flask.redirect('/settings')

@app.route('/t/<code>/upload/delete/<file_id>/')
def upload_delete(code, file_id):
    user_data = get_user_data(flask.session['username'])
    with open('../data/test_metadata/'+code+'.json') as f:
        test_metadata = parse_dict(f.read())
    if flask.session['username'] != test_metadata['owner']:
        if 'admin' in user_data['tags'] or 'team' in user_data['tags'] or check_sharing_perms(test_metadata, flask.session['username'])['files'] == True:
            pass
        else:
            return flask.render_template('401.html')
    shutil.rmtree('../data/test_data/'+code+'/files/'+file_id+'/')
    return flask.redirect('/t/'+code+'/upload/')

@app.route('/t/<code>/static/<file_code>/')
def t_static(code, file_code):
    return flask.send_file('../data/test_data/'+code+'/files/'+file_code+'/'+[f for f in os.listdir('../data/test_data/'+code+'/files/'+file_code) if os.path.isfile(os.path.join('../data/test_data/'+code+'/files/'+file_code, f))][0])

@app.route('/tg_auth/delete/')
def tg_auth_delete():
    try:
        with open('../data/telegram_username_credentials/'+flask.session['username']) as f:
            profile_id = f.read()
        os.remove('../data/telegram_username_credentials/'+flask.session['username'])
        os.remove('../data/telegram_credentials/'+profile_id)
        user_data = get_user_data(flask.session['username'])
        flask.session['settings_alert'] = 'Your Telegram account has been successfully unlinked'
        bot.send_message(profile_id, f"Hello *{user_data['name']}*!\nYour *Telegram account* has successfully been *unlinked at DAL Assessments*. You will no longer be able to receive notifcations from me.")
        return flask.redirect('/settings/')
    except FileNotFoundError:
        flask.session['settings_error'] = 'There was a problem unlinking your Telegram account'
        return flask.redirect('/settings/')

@app.route('/tg_auth/<loc>/')
def tg_auth(loc):
    data = dict(flask.request.args)
    if loc == 'auth':
        integrity = check_telegram_auth_data(data)
        if integrity == True:
            with open('../data/telegram_credentials/'+str(data['id']), 'w') as f:
                f.write(flask.session['username'])
            with open('../data/telegram_username_credentials/'+flask.session['username'], 'w') as f:
                f.write(str(data['id']))
            flask.session['settings_alert'] = 'Your Telegram account has successfully been linked'
            with open('../data/tg_bot_settings/'+flask.session['username'], 'w') as f:
                f.write(json.dumps({"on_login": True, "on_linked_accounts": True, "on_password_chane": True}))
            user_data = get_user_data(flask.session['username'])
            send_telegram_message(flask.session['username'], f'Hello *{user_data["name"]}*!\nYour *Telegram account* has successfully been *linked at DAL Assessments*. You will now be receiving notifications from me.', 'on_linked_accounts')
            return flask.redirect('/settings/')
        else:
            flask.session['settings_error'] = integrity
            return flask.redirect('/settings/')
    elif loc == 'signin':
        integrity = check_telegram_auth_data(data)
        if integrity == True:
            try:
                with open('../data/telegram_credentials/'+str(data['id'])) as f:
                    username = f.read()
                with open('../data/telegram_username_credentials/'+username) as g:
                    tg_id = g.read()
                if tg_id == data['id']:
                    flask.session['username'] = username
                    user_data = get_user_data(flask.session['username'])
                    flask.session['perm_auth_key'] = hashlib.sha256(user_data['password'].encode()).hexdigest()
                    user_data = get_user_data(flask.session['username'])
                    send_telegram_message(flask.session['username'], f'Dear *{user_data["name"]}*,\nThere is a *new login* with your *Telegram Account* at DAL Assessments.\n\n_If this wasn\'t you, please login quickly and change your password_', 'on_login')
                    return flask.redirect('/')
                else:
                    flask.session['login_error'] = 'There was an error while logging you in with Telegram. Please contact us soon.'
                    return flask.redirect('/login')
            except FileNotFoundError:
                flask.session['login_error'] = 'This Telegram Account has not been linked yet. Please use your password to log in.'
                return flask.redirect('/login')
        else:
            flask.session['login_error'] = integrity
            return flask.redirect('/login')
    return dict(flask.request.args)

#################### Error Handlers ####################

@app.errorhandler(404)
def e_404(e):
    return flask.render_template('404.html'), 404

@app.errorhandler(500)
def e_500(e):
    flask.session['error_referrer'] = flask.request.path
    return flask.render_template('500.html'), 500

#################### Other Endpoints ####################

@app.route('/robots.txt')
def robots_txt():
    return 'Telegram: @ChaitanyaPy, Github: https://github.com/ChaitanyaPy/'

@app.route('/update_server', methods=['post'])
def update_server():
    data = flask.request.json
    if check_hook_integrity(flask.request.headers.get('X-Real-IP')):
        pass
    else:
        return 'integrity failed'
    if data['action'] == 'closed' and data['pull_request']['merged'] == True:
        os.system('git pull')
        os.system('touch /var/www/diyaassessments_pythonanywhere_com_wsgi.py')
        return 'pulled and reloaded'
    return 'not pulled'

#################### Main ####################

# tg_bot_thread = threading.Thread(target=bot.polling)
# tg_bot_thread.start()

if __name__=='__main__':
    app.run(debug=True , port=80, host='0.0.0.0', threaded=True)
