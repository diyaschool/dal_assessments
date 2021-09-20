import textwrap
import httpagentparser
from os import listdir
from os.path import isfile, join
import json
import shutil
import datetime
import ast
import user_manager
import hashlib
import googleapis
import flask
import time
import os
import string
import random
import uuid
import ipaddress
from dateutil import tz
import base64
from collections import OrderedDict

#################### Initialize ####################

app = flask.Flask(__name__, static_url_path='/')

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

anonymous_urls = ['/favicon.ico', '/clear_test_cookies', '/logo.png',
                  '/background.png', '/loading.gif', '/update_server', '/privacy-policy', '/gauthtoken']
mobile_agents = ['Android', 'iPhone', 'iPod touch']

user_credentials = {}

from_zone = tz.tzlocal()
to_zone = tz.gettz('Asia/Kolkata')

#################### Utility Functions ####################


def curr_dt():
    dt = datetime.datetime.now()
    dt.replace(tzinfo=from_zone)
    dt = dt.astimezone(to_zone)
    return dt


def log_data(username, data):
    if os.path.isdir(f"../data/user_data/{username}/logs") == False:
        os.mkdir(f"../data/user_data/{username}/logs")
    dt = curr_dt()
    log = {}
    if data['type'] == 'login':
        path = f"../data/user_data/{username}/logs/auth.log"
        log['action'] = "login"
    elif data['type'] == 'logout':
        path = f"../data/user_data/{username}/logs/auth.log"
        log['action'] = "logout"
    elif data['type'] == 'passwd_change':
        path = f"../data/user_data/{username}/logs/passwd_change.log"
    elif data['linked_acc_change']:
        path = f"../data/user_data/{username}/logs/linked_acc_change.log"
    log['date'] = str(dt.date())
    log['time'] = str(dt.time())
    log['utime'] = str(time.time())
    log.update(data)
    with open(path, 'a') as f:
        f.write("\n" + json.dumps(log))


def list_to_csv(data):
    output_data = ""
    for row in data:
        for cell in row:
            output_data += str(cell) + ","
        output_data += "\n"
    return output_data


def convert_analytics_to_csv(data):
    output_data = []
    output_data.append(['#', 'Username', 'Name', 'Total Score', 'Average Time', 'Total Time', 'Time Stamp', 'Score (EZ)',
                       'Score (MID)', 'Score (HARD)', 'Percentage (EZ)', 'Percentage (MID)', 'Percentage (HARD)', 'Attempts'])
    for response in data:
        total_diff_scores_list = []
        for diff in response['difficulty_fraction']:
            total_diff_scores_list.append(f"{diff[0]}/{diff[1]}")
        total_diff_scores = " | ".join(total_diff_scores_list)
        total_diff_p_list = []
        for diff in response['difficulty_percentage']:
            if diff != None:
                total_diff_p_list.append(f"{diff}%")
            else:
                total_diff_p_list.append("null")
        total_diff_percentage = " | ".join(total_diff_p_list)
        if response.get('attempts') == None:
            attempts = f'Attempts 1'
        else:
            attempts = f'Attempts {response.get("attempts")}'
        total_diff_scores = total_diff_scores.replace(' ', '').split('|')
        total_diff_percentage = total_diff_percentage.replace(
            ' ', '').split('|')
        row_var = [response['index'], response['username'], response['name'], response['score'], response['average_time'], response['total_time'], response['long_time_stamp'],
                   total_diff_scores[0], total_diff_scores[1], total_diff_scores[2], total_diff_percentage[0], total_diff_percentage[1], total_diff_percentage[2], attempts]
        output_data.append(row_var)
    return output_data


def get_difficulty_percentage(data):
    output_data = [0, 0, 0]
    try:
        output_data[0] = int(data[0][0] / data[0][1] * 100)
    except ZeroDivisionError:
        output_data[0] = None
    try:
        output_data[1] = int(data[1][0] / data[1][1] * 100)
    except ZeroDivisionError:
        output_data[1] = None
    try:
        output_data[2] = int(data[2][0] / data[2][1] * 100)
    except ZeroDivisionError:
        output_data[2] = None
    return output_data


def get_difficulty_fraction(data):
    output_data = [[0, 0], [0, 0], [0, 0]]
    for question in data:
        if question['difficulty'] == 'easy':
            output_data[0][1] += 1
            if question['ans_res'] == True:
                output_data[0][0] += 1
        elif question['difficulty'] == 'medium':
            output_data[1][1] += 1
            if question['ans_res'] == True:
                output_data[1][0] += 1
        elif question['difficulty'] == 'hard':
            output_data[2][1] += 1
            if question['ans_res'] == True:
                output_data[2][0] += 1
    return output_data


def get_data_check_string(data):
    data = OrderedDict(sorted(data.items()))
    data_check_string = '\n'.join(
        ['%s=%s' % (key, value) for (key, value) in data.items() if key != 'hash'])
    return data_check_string


def parse_access_token_str(token_str):
    if token_str[:5] == 'error':
        return False
    _vars = str(token_str).split('&')
    access_token = _vars[0].split('=')[1]
    return access_token


def parse_dict(str_data):
    try:
        return json.loads(str_data)
    except json.decoder.JSONDecodeError:
        return ast.literal_eval(str_data)
    except SyntaxError:
        return False


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
        with open('../data/response_data/' + test_id + '.json') as f:
            data = parse_dict(f.read())
    except FileNotFoundError:
        return False
    for i, response in enumerate(data['responses']):
        if response['username'] == username:
            return str(i)
    return False


def save_test_response(username, test_id):
    user_data = get_user_data(username)
    with open('../data/user_data/' + username + '/test_data/' + test_id + '.json') as f:
        tdata = parse_dict(f.read())
    tdata['completed'] = True
    with open('../data/user_data/' + username + '/test_data/' + test_id + '.json', 'w') as f:
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
    data['average_time'] = round(sum(times) / len(times), 2)
    with open('../data/user_data/' + username + '/test_data/' + test_id + '.json') as f:
        data['question_stream'] = parse_dict(f.read())['question_stream']
    now = curr_dt()
    if now.hour > 12:
        c_m = 'PM'
        hour = now.hour - 12
    else:
        c_m = 'AM'
        hour = now.hour
    if now.hour == 12:
        c_m = 'PM'
        hour = hour
    if len(str(now.minute)) == 1:
        minute = '0' + str(now.minute)
    else:
        minute = now.minute
    with open('../data/test_metadata/' + test_id + '.json') as f:
        test_metadata = parse_dict(f.read())
    data["time_stamp"] = str(hour) + ":" + str(minute) + \
        ":" + str(now.second) + ' ' + c_m
    data["long_time_stamp"] = str(now.day) + "-" + str(now.month) + "-" + str(
        now.year) + " " + str(hour) + ":" + str(minute) + ":" + str(now.second) + ' ' + c_m
    if os.path.isdir('../data/user_data/' + username + '/response_data/') == False:
        os.makedirs('../data/user_data/' + username + '/response_data/')
    with open('../data/user_data/' + username + '/response_data/' + test_id + '.json', 'w') as f:
        with open('../data/test_data/' + test_id + '/config.json') as g:
            _ = parse_dict(g.read())
        f.write(json.dumps(
            {"time_stamp": data['time_stamp'], "long_time_stamp": data['long_time_stamp'], 'score': data['score'], "id": test_id}))
    response_id = get_user_response(username, test_id)
    if response_id != False:
        with open('../data/response_data/' + test_id + '.json') as f:
            cdata = parse_dict(f.read())
        cresponse_count = len(cdata['responses'])
        data['index'] = int(response_id) + 1
        try:
            data['attempts'] = cdata['responses'][int(
                response_id)]['attempts'] + 1
        except KeyError:
            data['attempts'] = 2
        cdata['responses'][int(response_id)] = data
        with open('../data/response_data/' + test_id + '.json', 'w') as f:
            f.write(json.dumps(cdata))
    else:
        try:
            with open('../data/response_data/' + test_id + '.json') as f:
                cdata = parse_dict(f.read())
            cresponse_count = len(cdata['responses'])
            with open('../data/user_data/' + test_metadata['owner'] + '/created_tests/' + test_id + '.json') as f:
                cr_fdata = parse_dict(f.read())
            cr_fdata['responses_count'] = len(cdata['responses']) + 1
            with open('../data/user_data/' + test_metadata['owner'] + '/created_tests/' + test_id + '.json', 'w') as f:
                f.write(json.dumps(cr_fdata))
            data['index'] = cresponse_count + 1
            data['attempts'] = 1
            cdata['responses'].append(data)
            with open('../data/response_data/' + test_id + '.json', 'w') as f:
                f.write(json.dumps(cdata))
        except FileNotFoundError:
            with open('../data/user_data/' + test_metadata['owner'] + '/created_tests/' + test_id + '.json') as f:
                cr_fdata = parse_dict(f.read())
            cr_fdata['responses_count'] = 1
            with open('../data/user_data/' + test_metadata['owner'] + '/created_tests/' + test_id + '.json', 'w') as f:
                f.write(json.dumps(cr_fdata))
            cdata = {}
            cdata['responses'] = []
            data['index'] = 1
            data['attempts'] = 1
            cdata['responses'].append(data)
            with open('../data/response_data/' + test_id + '.json', 'w') as f:
                f.write(json.dumps(cdata))


def delete_score(username, test_id):
    try:
        os.remove('../data/user_data/' + username +
                  '/test_data/' + test_id + '.json')
    except FileNotFoundError:
        pass


def update_score(username, test_id, ans_res, difficulty, question_id, answer_index, score, ans_score, time_taken):
    try:
        with open('../data/user_data/' + username + '/test_data/' + test_id + '.json') as f:
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
    now = curr_dt()
    if now.hour >= 12:
        c_m = 'PM'
        hour = now.hour - 12
    else:
        c_m = 'AM'
        hour = now.hour
    if len(str(now.minute)) == 1:
        minute = '0' + str(now.minute)
    else:
        minute = now.minute
    try:
        data['question_stream'].append({"difficulty": difficulty, "question_id": question_id, "question": test_data['questions'][difficulty][question_id]['question'], "given_answer": ans_given_text, "given_answer_index": answer_index, 'ans_res': ans_res, 'ans_score': ans_score, "time_taken": time_taken, "time_stamp": str(
            hour) + ":" + str(minute) + ":" + str(now.second) + ' ' + c_m, "long_time_stamp": str(now.day) + "-" + str(now.month) + "-" + str(now.year) + " " + str(hour) + ":" + str(minute) + ":" + str(now.second) + ' ' + c_m, "index": len(data['question_stream']) + 1})
    except KeyError:
        data['question_stream'] = []
        data['question_stream'].append({"difficulty": difficulty, "question_id": question_id, "question": test_data['questions'][difficulty][question_id]['question'], "given_answer": ans_given_text, "given_answer_index": answer_index, 'ans_res': ans_res, 'ans_score': ans_score,
                                       "time_taken": time_taken, "time_stamp": str(hour) + ":" + str(minute) + ":" + str(now.second) + ' ' + c_m, "long_time_stamp": str(now.day) + "-" + str(now.month) + "-" + str(now.year) + " " + str(hour) + ":" + str(minute) + ":" + str(now.second) + ' ' + c_m, "index": 1})
    data['score'] = score
    with open('../data/user_data/' + username + '/test_data/' + test_id + '.json', 'w') as f:
        f.write(json.dumps(data))
    return True


def get_user_data(user_id):
    try:
        with open('../data/user_metadata/' + user_id) as f:
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


def convert(sheet, teacher=False):
    try:
        sheet = sheet[1:]
        sheet = row_to_column(sheet)
        output = {}
        output['test_name'] = sheet[0][0]
        output['subject'] = sheet[0][1]
        if teacher == True:
            sheet[1] = [x for x in sheet[1] if x]
            output['tags'] = sheet[1]
            if 'all' in sheet[1]:
                output['tags'] = ['all']
        else:
            output['tags'] = ['all']
        output['questions'] = {"easy": [], "medium": [], "hard": []}
        for i in range(len(sheet[2])):
            if sheet[2][i] == '':
                continue
            c_a_i = parse_dict(sheet[4][i]) - 1
            if sheet[5][i] == '':
                output['questions']['easy'].append(
                    {"question": sheet[2][i], "answers": sheet[3][i].split('\n'), "correct_answer_index": c_a_i})
            else:
                output['questions']['easy'].append({"question": sheet[2][i], "answers": sheet[3][i].split(
                    '\n'), "correct_answer_index": c_a_i, "image": sheet[5][i]})
        for i in range(len(sheet[6])):
            if sheet[6][i] == '':
                continue
            c_a_i = parse_dict(sheet[8][i]) - 1
            if sheet[9][i] == '':
                output['questions']['medium'].append(
                    {"question": sheet[6][i], "answers": sheet[7][i].split('\n'), "correct_answer_index": c_a_i})
            else:
                output['questions']['medium'].append({"question": sheet[6][i], "answers": sheet[7][i].split(
                    '\n'), "correct_answer_index": c_a_i, "image": sheet[9][i]})
        for i in range(len(sheet[10])):
            if sheet[10][i] == '':
                continue
            c_a_i = parse_dict(sheet[12][i]) - 1
            try:
                if sheet[13][i] == '':
                    output['questions']['hard'].append(
                        {"question": sheet[10][i], "answers": sheet[11][i].split('\n'), "correct_answer_index": c_a_i})
                else:
                    output['questions']['hard'].append({"question": sheet[10][i], "answers": sheet[11][i].split(
                        '\n'), "correct_answer_index": c_a_i, "image": sheet[13][i]})
            except IndexError:
                output['questions']['hard'].append(
                    {"question": sheet[10][i], "answers": sheet[11][i].split('\n'), "correct_answer_index": c_a_i})
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
    except Exception as e:
        return "ERROR"


def create_new_test_sheet(owner):
    dt = curr_dt()
    c_time = str(dt.hour) + ':' + str(dt.minute) + ':' + str(dt.second)
    c_date = str(dt.year) + '-' + str(dt.month) + '-' + str(dt.day)
    test_list = [f for f in os.listdir(
        '../data/test_data') if os.path.isdir(os.path.join('../data/test_data', f))]
    while 1:
        r_id = id_generator()
        if r_id in test_list:
            pass
        else:
            break
    test_id = r_id
    # sheet_id = googleapis.create_sheet(test_id, creds)
    os.mkdir('../data/test_data/' + test_id)
    os.mkdir('../data/test_data/' + test_id + '/files')
    with open('../data/test_data/' + test_id + '/config.json', 'w') as f:
        f.write(json.dumps({"test_name": "", "subject": "",
                "tags": [], "question_count": 0, "visibility": True}))
    with open('../data/test_metadata/' + test_id + '.json', 'w') as f:
        f.write(json.dumps({"owner": owner, "time": c_time,
                "date": c_date, "last_time": c_time, "last_date": c_date}))
    with open('../data/user_data/' + owner + '/created_tests/' + test_id + '.json', 'w') as f:
        f.write(json.dumps({"last_time": c_time, "last_date": c_date,
                "name": "Undefined", "subject": "Undefined", "responses_count": 0}))
    return test_id


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
        with open('../data/test_data/' + test_id + '/config.json') as f:
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


def delete_test(test_id):
    with open('../data/test_metadata/' + test_id + '.json') as f:
        metadata = parse_dict(f.read())
    owner = metadata['owner']
    try:
        os.remove('../data/user_data/' + owner +
                  '/created_tests/' + test_id + '.json')
    except FileNotFoundError:
        pass
    try:
        os.remove('../data/user_data/' + owner +
                  '/response_data/' + test_id + '.json')
    except FileNotFoundError:
        pass
    try:
        with open('../data/user_data/' + owner + '/google_sheets_analytics_records') as f:
            g_sheets_records = parse_dict(f.read())
        try:
            g_sheets_records.pop(test_id)
        except KeyError:
            pass
        with open('../data/user_data/' + owner + '/google_sheets_analytics_records', 'w') as f:
            f.write(json.dumps(g_sheets_records))
    except FileNotFoundError:
        pass
    os.remove('../data/test_metadata/' + test_id + '.json')
    with open('../data/test_data/' + test_id + '/config.json') as f:
        try:
            test_data = parse_dict(f.read())
        except SyntaxError:
            test_data = False
    if test_data != False:
        tags = test_data['tags']
        for tag in tags:
            if tag == '':
                continue
            try:
                with open('../data/global_test_records/' + tag) as f:
                    test_record = parse_dict(f.read())
                try:
                    test_record.pop(test_id)
                    with open('../data/global_test_records/' + tag, 'w') as f:
                        f.write(json.dumps(test_record))
                except KeyError:
                    pass
            except FileNotFoundError:
                pass
    try:
        os.remove('../data/response_data/' + test_id + '.json')
    except FileNotFoundError:
        pass
    shutil.rmtree('../data/test_data/' + test_id)


def get_created_tests_list(username):
    created_test_list = [f for f in os.listdir('../data/user_data/' + username + '/created_tests') if os.path.isfile(
        os.path.join('../data/user_data/' + username + '/created_tests', f))]
    created_tests = []
    for test in created_test_list:
        with open('../data/user_data/' + username + '/created_tests/' + test) as f:
            created_tests.append(parse_dict(f.read()))
    sort_prep_list = []
    for i, test in enumerate(created_tests):
        test['id'] = created_test_list[i][:-5]
        temp_id = id_generator(5)
        sort_prep_list.append(test['last_date'] +
                              ' ' + test['last_time'] + ' ' + temp_id)
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


def get_current_tests_list(username):
    user_data = get_user_data(username)
    test_id_list = []
    for tag in user_data['tags']:
        try:
            with open('../data/global_test_records/' + tag) as f:
                fdata = parse_dict(f.read())
            test_id_list.extend(list(fdata.keys()))
        except FileNotFoundError:
            pass
    try:
        with open('../data/global_test_records/all') as f:
            fdata = parse_dict(f.read())
        test_id_list.extend(list(fdata.keys()))
    except FileNotFoundError:
        pass
    completed_list = get_completed_tests_list(username)
    for test in completed_list:
        if test['id'] in test_id_list:
            test_id_list.remove(test['id'])
    test_data = []
    for test in test_id_list:
        temp = {}
        with open('../data/test_data/' + test + '/config.json') as f:
            fdata = parse_dict(f.read())
        temp['id'] = test
        temp['name'] = fdata['test_name']
        temp['subject'] = fdata['subject']
        temp['total_questions'] = fdata['question_count']
        test_data.append(temp)
    return test_data


def get_completed_tests_list(username):
    try:
        tests = [f for f in listdir('../data/user_data/' + username + '/response_data/')
                 if isfile(join('../data/user_data/' + username + '/response_data/', f))]
    except FileNotFoundError:
        return []
    output = []
    for test in tests:
        try:
            with open('../data/user_data/' + username + '/response_data/' + test) as f:
                fdata = parse_dict(f.read())
                temp = fdata.copy()
            with open('../data/test_data/' + os.path.splitext(test)[0] + '/config.json') as f:
                fdata = parse_dict(f.read())
            temp['name'] = fdata['test_name']
            temp['subject'] = fdata['subject']
            output.append(temp)
        except FileNotFoundError:
            continue
    return output


def editor_data_to_test_data(editor_data):
    for div in editor_data_raw:
        question = editor_data_raw[div]
        if question['difficulty'] == 'mid':
            question['difficulty'] = 'medium'
        for i, option in enumerate(question['options']):
            question['options'][i] = option.strip()
        editor_data[question['difficulty']].append({'question': question['question'].strip(
        ), 'answers': question['options'], 'correct_answer_index': question['c_a_i']})


def validate_test_data_raw(test_data):
    try:
        test_data['questions']
        if len(test_data['questions']['easy']) == 0:
            return {"success": False}
        if len(test_data['questions']['medium']) == 0:
            return {"success": False}
        if len(test_data['questions']['hard']) == 0:
            return {"success": False}
        for q in test_data['questions']['easy']:
            if q['question'] == '':
                return {"success": False}
            for o in q['answers']:
                if o == '':
                    return {"success": False}
        for q in test_data['questions']['medium']:
            if q['question'] == '':
                return {"success": False}
            for o in q['answers']:
                if o == '':
                    return {"success": False}
        for q in test_data['questions']['hard']:
            if q['question'] == '':
                return {"success": False}
            for o in q['answers']:
                if o == '':
                    return {"success": False}
        return {"success": True}
    except KeyError:
        return {"success": False}

#################### Reqeust Handlers ####################


@app.before_request
def before_request():
    print(flask.request.headers)
    if flask.request.headers['Host'] not in DOMAINS:
        return flask.redirect('https://google.com/', 301)
    onlyfiles = [f for f in listdir('static/') if isfile(join('static/', f))]
    if flask.request.path != '/login' and flask.request.path not in anonymous_urls and flask.request.path.strip("/") not in onlyfiles:
        try:
            username = flask.session['username']
            f = open('../data/user_metadata/' + username)
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
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def sanitize_input(in_data):
    in_data.replace('.', '')
    in_data.replace('/', '')
    in_data.replace('\\', '')
    return in_data

#################### Context Processors ####################


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
    current_tests = get_current_tests_list(flask.session['username'])
    completed_tests = get_completed_tests_list(flask.session['username'])
    created_tests = get_created_tests_list(flask.session['username'])
    if desktop:
        return flask.render_template('home.html', username=flask.session['username'], name=user_data['name'], created_tests=created_tests, created_tests_len=len(created_tests), current_tests=current_tests, current_tests_len=len(current_tests), completed_tests=completed_tests, completed_tests_len=len(completed_tests))
    else:
        return flask.render_template('mobile/home.html', username=flask.session['username'], name=user_data['name'], created_tests=created_tests, created_tests_len=len(created_tests), current_tests=current_tests, current_tests_len=len(current_tests), completed_tests=completed_tests, completed_tests_len=len(completed_tests))

@app.route('/about')
def about():
    user_data = get_user_data(flask.session['username'])
    return flask.render_template("about.html", username=flask.session['username'], name=user_data['name'])


@app.route('/logout')
def logout():
    flask.session.pop('username')
    flask.session.pop('perm_auth_key')
    flask.session.modified = True
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
    code = sanitize_input(code)
    data = flask.request.form
    if str(data['answer']) == str(flask.session['t']['c_a_i']):
        flask.session['t']['prev_q_res'] = True
    else:
        flask.session['t']['prev_q_res'] = False
    if flask.session['t']['prev_q_res'] == True:
        if flask.session['t']['difficulty'] == 0:
            ans_score = 1
        elif flask.session['t']['difficulty'] == 1:
            ans_score = 3
        elif flask.session['t']['difficulty'] == 2:
            ans_score = 5
        flask.session['t']['score'] = str(parse_dict(
            flask.session['t']['score']) + ans_score)
    else:
        ans_score = 0
    flask.session['t']['verified'] = True
    time_taken = time.time() - flask.session['t']['time']
    update_score(flask.session['username'], code, flask.session['t']['prev_q_res'], flask.session['t']['difficulty'],
                 flask.session['t']['q_id'], parse_dict(data['answer']), flask.session['t']['score'], ans_score, time_taken)
    flask.session['t']['q'] = str(parse_dict(flask.session['t']['q']) + 1)
    flask.session.modified = True
    return flask.redirect('/t/' + code)


@app.route('/t/<code>/')
def t_view(code):
    code = sanitize_input(code)
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
    with open('../data/test_metadata/' + code + '.json') as f:
        test_metadata = parse_dict(f.read())
    if check_sharing_perms(test_metadata, flask.session['username'])['attend'] == True:
        authorized = True
    if authorized == False:
        return flask.render_template('401.html'), 401
    if test_metadata.get('enable') == True or test_metadata.get('enable') == None:
        pass
    else:
        if desktop:
            return flask.render_template('t_disabled.html')
        else:
            # return flask.render_template('mobile/t_disabled.html')
            return flask.render_template('t_disabled.html')
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
        return flask.redirect('/t/' + code)
    if flask.request.args.get('start') == '':
        try:
            flask.session['t']['q'] = '1'
            flask.session.modified = True
        except KeyError:
            return flask.redirect('/t/' + code)
        return flask.redirect('/t/' + code)
    elif flask.request.args.get('exit') == '':
        flask.session.pop('t')
        flask.session.modified = True
        delete_score(flask.session['username'], code)
        return flask.redirect('/t/' + code)
    if len(flask.session['t']['c_q'][0]) == len(question_data['questions']['easy']) and len(flask.session['t']['c_q'][1]) == len(question_data['questions']['medium']) and len(flask.session['t']['c_q'][2]) == len(question_data['questions']['hard']):
        score = flask.session['t']['score']
        flask.session.pop('t')
        flask.session.modified = True
        save_test_response(flask.session['username'], code)
        delete_score(flask.session['username'], code)
        if desktop:
            return flask.render_template('t_completed.html', test_name=question_data['test_name'], score=score, name=user_data['name'], username=flask.session['username'], code=code)
        else:
            return flask.render_template('mobile/t_completed.html', test_name=question_data['test_name'], score=score, name=user_data['name'], username=flask.session['username'], code=code)
    else:
        if question_data['question_count'] == parse_dict(flask.session['t']['q']) - 1:
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
                with open('../data/user_metadata/' + flask.session['username'], 'w') as f:
                    f.write(json.dumps(user_data))
            save_test_response(flask.session['username'], code)
            delete_score(flask.session['username'], code)
            if desktop:
                return flask.render_template('t_completed.html', test_name=question_data['test_name'], score=score, name=user_data['name'], username=flask.session['username'], code=code)
            else:
                return flask.render_template('mobile/t_completed.html', test_name=question_data['test_name'], score=score, name=user_data['name'], username=flask.session['username'], code=code)
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
                question = get_question(
                    flask.session['t']['c_q'][1], question_data['questions']['medium'])
                if question == "QUESTIONS_COMPLETED":
                    question = get_question(
                        flask.session['t']['c_q'][0], question_data['questions']['easy'])
                    if question == "QUESTIONS_COMPLETED":
                        question = get_question(
                            flask.session['t']['c_q'][2], question_data['questions']['hard'])
                        flask.session['t']['difficulty'] = 2
                    else:
                        flask.session['t']['difficulty'] = 0
                else:
                    flask.session['t']['difficulty'] = 1
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
                return flask.render_template('t.html', code=code, question_data=question, ans_range=range(len(question['answers'])), data=question_data, q_number=q_number, image_url=image_url, username=flask.session['username'], name=user_data['name'], total_height=650 + height_extend, answers=o_answers)
            else:
                return flask.render_template('mobile/t.html', code=code, question_data=question, ans_range=range(len(question['answers'])), data=question_data, q_number=q_number, image_url=image_url, username=flask.session['username'], name=user_data['name'], total_height=650 + height_extend, answers=o_answers)
        else:
            try:
                if flask.session['t'].get('verified') == True:
                    prev_q_res = flask.session['t']['prev_q_res']
                    flask.session['t'].pop('prev_q_res')
                    flask.session['t']['time'] = time.time()
                    c_difficulty = get_difficulty(
                        flask.session['t']['difficulty'], flask.session['t']['c_q'], question_data['questions'], prev_q_res)
                    flask.session['t']['difficulty'] = c_difficulty
                    if c_difficulty == 0:
                        question = get_question(
                            flask.session['t']['c_q'][0], question_data['questions']['easy'])
                    elif c_difficulty == 1:
                        question = get_question(
                            flask.session['t']['c_q'][1], question_data['questions']['medium'])
                    elif c_difficulty == 2:
                        question = get_question(
                            flask.session['t']['c_q'][2], question_data['questions']['hard'])
                    flask.session['t']['q_id'] = question['id']
                    if question == 'QUESTIONS_COMPLETED':
                        return flask.render_template('500.html'), 500
                    flask.session['t']['c_q'][c_difficulty].append(
                        question['id'])
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
                return flask.render_template('t.html', code=code, question_data=question, ans_range=range(len(question['answers'])), data=question_data, q_number=q_number, image_url=image_url, username=flask.session['username'], name=user_data['name'], total_height=650 + height_extend, answers=o_answers)
            else:
                return flask.render_template('mobile/t.html', code=code, question_data=question, ans_range=range(len(question['answers'])), data=question_data, q_number=q_number, image_url=image_url, username=flask.session['username'], name=user_data['name'], total_height=650 + height_extend, answers=o_answers)


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
        if desktop:
            return flask.render_template('login.html', error=error, username='')
        else:
            return flask.render_template('mobile/login.html', error=error, username='')
    elif flask.request.method == 'POST':
        form_data = flask.request.form.copy()
        form_data['username'] = form_data['username'].lower()
        try:
            with open('../data/user_metadata/' + form_data['username'].lower()) as f:
                fdata = f.read()
            data = parse_dict(fdata)
            password = hashlib.sha224(
                form_data['password'].encode()).hexdigest()
            if data['password'] != password:
                if desktop:
                    return flask.render_template('login.html', error='Invalid Credentials', username=form_data['username'])
                else:
                    return flask.render_template('mobile/login.html', error='Invalid Credentials', username=form_data['username'])
            else:
                flask.session['username'] = form_data['username'].lower()
                user_data = get_user_data(flask.session['username'])
                flask.session['perm_auth_key'] = hashlib.sha256(
                    user_data['password'].encode()).hexdigest()
                user_data = get_user_data(flask.session['username'])
                ip = flask.request.headers.get('X-Real-IP')
                if ip == None:
                    ip = flask.request.remote_addr
                ua = flask.request.headers.get('User-Agent')
                ua = httpagentparser.detect(ua)
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
                return flask.render_template('login.html', error='Invalid Credentials', username=form_data['username'])
            else:
                return flask.render_template('mobile/login.html', error='Invalid Credentials', username=form_data['username'])


@app.route('/new_test', methods=['GET', 'POST'])
def new_test():
    user_data = get_user_data(flask.session['username'])
    if flask.request.method == 'GET':
        return flask.render_template('new_test.html', username=flask.session['username'], name=user_data['name'])
    else:
        test_id = create_new_test_sheet(flask.session['username'])
        return flask.redirect('/t/' + test_id + '/edit/editor/')


@app.route('/t/<code>/edit/delete/', methods=['GET'])
def test_edit_delete(code):
    code = sanitize_input(code)
    try:
        with open('../data/test_metadata/' + code + '.json') as f:
            data = parse_dict(f.read())
    except:
        return flask.render_template('404.html'), 404
    user_data = get_user_data(flask.session['username'])
    if data['owner'] == flask.session['username'] or 'admin' in user_data['tags'] or 'team' in user_data['tags'] or check_sharing_perms(data, flask.session['username'])['edit'] == True:
        pass
    else:
        return flask.redirect('/t/' + code)
    delete_test(code)
    return flask.redirect('/')


@app.route('/t/<code>/edit/', methods=['GET'])
def test_edit(code):
    code = sanitize_input(code)
    return flask.redirect("/t/" + code + "/edit/editor/", 301)


@app.route('/t/<code>/analytics/')
def test_analytics(code):
    code = sanitize_input(code)
    user_data = get_user_data(flask.session['username'])
    try:
        with open('../data/test_metadata/' + code + '.json') as f:
            data = parse_dict(f.read())
    except:
        return flask.render_template('404.html'), 404
    if data['owner'] == flask.session['username'] or 'admin' in user_data['tags'] or 'team' in user_data['tags'] or check_sharing_perms(data, flask.session['username'])['overview-analytics'] == True:
        pass
    else:
        if 'teacher' in user_data['tags']:
            return flask.render_template('401.html'), 401
        else:
            return flask.redirect('/t/' + code)
    with open('../data/test_data/' + code + '/config.json') as f:
        test_data = f.read()
    try:
        title = parse_dict(test_data)['test_name']
    except KeyError:
        return "The test was not properly created. Please contact the owner of this test."
    except SyntaxError:
        return "The test was not properly created. Please contact the owner of this test."
    try:
        with open('../data/response_data/' + code + '.json') as f:
            response_data = parse_dict(f.read())
    except FileNotFoundError:
        response_data = {'responses': []}
    for user in response_data['responses']:
        user['difficulty_fraction'] = get_difficulty_fraction(
            user['question_stream'])
        user['difficulty_percentage'] = get_difficulty_percentage(
            user['difficulty_fraction'])
    alert = flask.session.get('analytics_alert')
    if alert == None:
        alert = 'none'
    try:
        flask.session.pop('analytics_alert')
    except KeyError:
        pass
    open_redirect = flask.session.get('analytics_redirect')
    if open_redirect == None:
        open_redirect = 'none'
    try:
        flask.session.pop('analytics_redirect')
    except KeyError:
        pass
    return flask.render_template('test_analytics.html', test_name=title, username=flask.session['username'], name=user_data['name'], responses=response_data['responses'], response_count=len(response_data['responses']), code=code, alert=alert, open_redirect=open_redirect)


@app.route('/t/<code>/analytics_download/<mode>')
def test_analytics_download(code, mode):
    code = sanitize_input(code)
    mode = sanitize_input(mode)
    user_data = get_user_data(flask.session['username'])
    try:
        with open('../data/test_metadata/' + code + '.json') as f:
            data = parse_dict(f.read())
    except:
        return flask.render_template('404.html'), 404
    if data['owner'] == flask.session['username'] or 'admin' in user_data['tags'] or 'team' in user_data['tags'] or check_sharing_perms(data, flask.session['username'])['overview-analytics'] == True:
        pass
    else:
        if 'teacher' in user_data['tags']:
            return flask.render_template('401.html'), 401
        else:
            return flask.redirect('/t/' + code)
    with open('../data/test_data/' + code + '/config.json') as f:
        test_data = f.read()
    try:
        title = parse_dict(test_data)['test_name']
    except KeyError:
        return "The test was not properly created. Please contact the owner of this test."
    except SyntaxError:
        return "The test was not properly created. Please contact the owner of this test."
    try:
        with open('../data/response_data/' + code + '.json') as f:
            response_data = parse_dict(f.read())
    except FileNotFoundError:
        response_data = {'responses': []}
    for user in response_data['responses']:
        user['difficulty_fraction'] = get_difficulty_fraction(
            user['question_stream'])
        user['difficulty_percentage'] = get_difficulty_percentage(
            user['difficulty_fraction'])
    csv_data = convert_analytics_to_csv(response_data['responses'])
    if mode == 'csv':
        csv_data_str = list_to_csv(csv_data)
        return flask.Response(csv_data_str, mimetype="text/csv", headers={"Content-disposition": f"attachment; filename={title} - Analytics.csv"})
    elif mode == 'google_sheets':
        try:
            with open('../data/user_data/' + flask.session['username'] + '/google_sheets_analytics_records') as f:
                gdata = parse_dict(f.read())
            if gdata == False:
                gdata = {}
        except FileNotFoundError:
            gdata = {}
        if gdata.get(code) == None:
            gauth = googleapis.authorize()
            creds = gauth.load_credentials(flask.session['username'])
            if creds == None:
                flask.session['settings_alert'] = 'Please link your Google account before creating a test'
                return flask.request.url_root + 'settings'
            sheet_id = googleapis.create_data_sheet(
                f"{title} - Analytics", creds, csv_data)
            gdata[code] = sheet_id
            with open('../data/user_data/' + flask.session['username'] + '/google_sheets_analytics_records', 'w') as f:
                f.write(json.dumps(gdata))
            flask.session['analytics_alert'] = "Generated Google Sheet"
        else:
            gauth = googleapis.authorize()
            creds = gauth.load_credentials(flask.session['username'])
            print(creds)
            if creds == None:
                flask.session['settings_alert'] = 'Please link your Google account before creating a test'
                return flask.request.url_root + 'settings'
            sheet_id = googleapis.update_sheet(gdata[code], creds, csv_data)
            flask.session['analytics_alert'] = "Generated Google Sheet"
            if sheet_id == False:
                sheet_id = googleapis.create_data_sheet(
                    f"{title} - Analytics", creds, csv_data)
                gdata[code] = sheet_id
                with open('../data/user_data/' + flask.session['username'] + '/google_sheets_analytics_records', 'w') as f:
                    f.write(json.dumps(gdata))
                flask.session['analytics_alert'] = "Re-generated Google Sheet"
        # flask.session['analytics_redirect'] = 'https://docs.google.com/spreadsheets/d/'+sheet_id
        # return flask.redirect('/t/'+code+'/analytics/')
        return 'https://docs.google.com/spreadsheets/d/' + sheet_id


@app.route('/t/<code>/analytics/<username>/')
def test_analytics_user(code, username):
    code = sanitize_input(code)
    username = sanitize_input(username)
    auserdata = get_user_data(username)
    user_data = get_user_data(flask.session['username'])
    try:
        with open('../data/test_metadata/' + code + '.json') as f:
            data = parse_dict(f.read())
    except:
        return flask.render_template('404.html'), 404
    admin = False
    if data['owner'] == flask.session['username'] or 'admin' in user_data['tags'] or 'team' in user_data['tags'] or check_sharing_perms(data, flask.session['username'])['overview-analytics'] == True or username == flask.session['username']:
        admin = True
    else:
        if 'teacher' in user_data['tags']:
            return flask.render_template('401.html'), 401
        else:
            return flask.redirect('/t/' + code)
    with open('../data/test_data/' + code + '/config.json') as f:
        test_data = f.read()
    try:
        title = parse_dict(test_data)['test_name']
    except KeyError:
        return "The test was not properly created. Please contact the owner of this test."
    except SyntaxError:
        return "The test was not properly created. Please contact the owner of this test."
    with open('../data/response_data/' + code + '.json') as f:
        fdata = parse_dict(f.read())['responses'][int(
            get_user_response(username, code))]
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
            response['question'] = response['question'][:20] + '...'
        response['full_given_answer'] = response['given_answer']
        if len(response['given_answer']) > 20:
            response['given_answer'] = response['given_answer'][:20] + '...'
    try:
        fdata['attempts']
        attempts = True
    except:
        attempts = False
    desktop = True
    for agent in mobile_agents:
        if agent in flask.request.headers['User-Agent']:
            desktop = False
    if desktop:
        return flask.render_template('test_analytics_username.html', test_name=title, username=flask.session['username'], name=user_data['name'], responses=response_data, response_count=len(response_data), code=code, auserdata=auserdata, score=score, fdata=fdata, attempts_bool=attempts, admin=admin)
    else:
        return flask.render_template('mobile/test_analytics_username.html', test_name=title, username=flask.session['username'], name=user_data['name'], responses=response_data, response_count=len(response_data), code=code, auserdata=auserdata, score=score, fdata=fdata, attempts_bool=attempts, admin=admin)


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
                    user_manager.change_password(
                        flask.session['username'], data['new_password'])
                    flask.session['perm_auth_key'] = hashlib.sha256(hashlib.sha224(
                        data['new_password'].encode()).hexdigest().encode()).hexdigest()
                    if user_data.get('has_changed_password') == None:
                        pass
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
        google_auth = False
        gauth = googleapis.authorize()
        creds = gauth.load_credentials(flask.session['username'])
        if creds != None:
            google_auth = True
        desktop = True
        for agent in mobile_agents:
            if agent in flask.request.headers['User-Agent']:
                desktop = False
        if desktop:
            return flask.render_template('settings.html', username=flask.session['username'], name=user_data['name'], error=error, alert=alert, google_auth=google_auth)
        else:
            return flask.render_template('mobile/settings.html', username=flask.session['username'], name=user_data['name'], error=error, alert=alert, google_auth=google_auth)
    elif flask.request.method == 'POST':
        data = flask.request.form
        if flask.request.args.get('change_password') == '':
            if hashlib.sha224(data['current_password'].encode()).hexdigest() == user_data['password']:
                if data['new_password'] == data['conf_password']:
                    if data['current_password'] != data['new_password']:
                        user_manager.change_password(
                            flask.session['username'], data['new_password'])
                        flask.session['perm_auth_key'] = hashlib.sha256(hashlib.sha224(
                            data['new_password'].encode()).hexdigest().encode()).hexdigest()
                        flask.session['settings_alert'] = 'Your password has been changed successfully'
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


@app.route('/sheets_api_authorize/', methods=['GET', 'POST'])
def sheets_api_authorize():
    global user_credentials
    user_data = get_user_data(flask.session['username'])
    if flask.request.method == 'GET':
        try:
            user_credentials.pop(flask.session['username'])
        except KeyError:
            pass
        gauth = googleapis.authorize()
        creds = gauth.load_credentials(flask.session['username'])
        user_credentials[flask.session['username']] = gauth
        if creds:
            flask.session['settings_alert'] = 'You have already linked your Google Account'
            return flask.redirect('/settings')
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
            return flask.redirect('/settings')
        else:
            user_credentials.pop(flask.session['username'])
            flask.session['settings_error'] = 'There was an error during authorization'
            return flask.redirect('/settings')


@app.route('/sheets_api_authorize/delete/')
def sheets_api_authorize_delete():
    try:
        _ = get_user_data(flask.session['username'])
        os.remove('../data/credentials/' +
                  flask.session['username'] + '.pickle')
        flask.session['settings_alert'] = 'Your Google account has been successfully unlinked'
        return flask.redirect('/settings')
    except FileNotFoundError:
        flask.session['settings_error'] = 'There was a problem unlinking your Google account'
        return flask.redirect('/settings')


@app.route('/upload_file/<code>')
def u_r(code):
    return flask.render_template('u_r.html', code=code)


@app.route('/t/<code>/upload/', methods=['POST'])
def upload_file(code):
    code = sanitize_input(code)
    user_data = get_user_data(flask.session['username'])
    try:
        with open('../data/test_metadata/' + code + '.json') as f:
            data = parse_dict(f.read())
    except FileNotFoundError:
        return flask.render_template('404.html'), 404
    if data['owner'] == flask.session['username'] or 'admin' in user_data['tags'] or 'team' in user_data['tags'] or check_sharing_perms(data, flask.session['username'])['edit'] == True:
        pass
    else:
        return flask.redirect('/t/' + code)
    print(flask.request.form)
    print(flask.request.files)
    f = flask.request.files['file']
    test_list = [f for f in os.listdir('../data/test_data/' + code + '/files/')
                 if os.path.isdir(os.path.join('../data/test_data/' + code + '/files/', f))]
    while 1:
        r_id = id_generator()
        if r_id in test_list:
            pass
        else:
            break
    file_id = r_id.lower()
    if f.filename.strip() == "":
        return "file name not ok", 401
    os.mkdir('../data/test_data/' + code + '/files/' + file_id)
    f.save('../data/test_data/' + code +
           '/files/' + file_id + '/' + f.filename)
    try:
        with open('../data/t_editor_data/' + code + '.json') as f:
            fdata = parse_dict(f.read())
    except FileNotFoundError:
        fdata = {}
    fdata[flask.request.form['div_id']]['image'] = file_id
    with open('../data/t_editor_data/' + code + '.json', 'w') as f:
        f.write(json.dumps(fdata))
    return file_id


@app.route('/t/<code>/upload/delete/<file_id>/')
def upload_delete(code, file_id):
    code = sanitize_input(code)
    file_id = sanitize_input(file_id)
    user_data = get_user_data(flask.session['username'])
    with open('../data/test_metadata/' + code + '.json') as f:
        test_metadata = parse_dict(f.read())
    if flask.session['username'] != test_metadata['owner']:
        if 'admin' in user_data['tags'] or 'team' in user_data['tags'] or check_sharing_perms(test_metadata, flask.session['username'])['files'] == True:
            pass
        else:
            return flask.render_template('401.html')
    shutil.rmtree('../data/test_data/' + code + '/files/' + file_id + '/')
    return flask.redirect('/t/' + code + '/upload/')


@app.route('/t/<code>/static/<file_code>/')
def t_static(code, file_code):
    if os.path.isdir('../data/test_data/' + code + '/files/' + file_code) == True:
        return flask.send_file('../data/test_data/' + code + '/files/' + file_code + '/' + [f for f in os.listdir('../data/test_data/' + code + '/files/' + file_code) if os.path.isfile(os.path.join('../data/test_data/' + code + '/files/' + file_code, f))][0])
    return "File not found"


@app.route('/t/<code>/edit/editor/', methods=['GET', 'POST'])
def test_edit_editor(code):
    code = sanitize_input(code)
    user_data = get_user_data(flask.session['username'])
    try:
        with open('../data/test_metadata/' + code + '.json') as f:
            data = parse_dict(f.read())
    except:
        return flask.render_template('404.html'), 404
    if data['owner'] == flask.session['username'] or 'admin' in user_data['tags'] or 'team' in user_data['tags'] or check_sharing_perms(data, flask.session['username'])['edit'] == True:
        pass
    else:
        return flask.redirect('/t/' + code)
    try:
        with open('../data/test_metadata/' + code + '.json') as f:
            data = parse_dict(f.read())
    except:
        return flask.render_template('404.html'), 404
    with open('../data/test_data/' + code + '/config.json') as f:
        try:
            test_data = parse_dict(f.read())
            title = test_data['test_name']
        except SyntaxError:
            test_data = {}
            test_data['tags'] = []
            title = 'Untitled'
    if data['owner'] == flask.session['username'] or 'admin' in user_data['tags'] or 'team' in user_data['tags'] or check_sharing_perms(data, flask.session['username'])['edit'] == True:
        pass
    else:
        return flask.redirect('/t/' + code)
    return flask.render_template('editor.html', code=code, data=data, test_data=test_data, title=title, username=flask.session['username'], name=user_data['name'])

#################### API Endpoints ####################


@app.route('/t/<code>/edit/api/load_metadata')
def t_edit_api_load_metadata(code):
    code = sanitize_input(code)
    user_data = get_user_data(flask.session['username'])
    try:
        with open('../data/test_metadata/' + code + '.json') as f:
            data = parse_dict(f.read())
    except FileNotFoundError:
        return flask.render_template('404.html'), 404
    if data['owner'] == flask.session['username'] or 'admin' in user_data['tags'] or 'team' in user_data['tags'] or check_sharing_perms(data, flask.session['username'])['edit'] == True:
        pass
    else:
        return flask.redirect('/t/' + code)
    with open('../data/test_data/' + code + '/config.json') as f:
        test_data = parse_dict(f.read())
    visibility = test_data.get('visibility')
    if visibility == None:
        visibility = True
    return {"title": test_data['test_name'], "tags": ",".join(test_data['tags']), "subject": test_data['subject'], 'total_questions': test_data['question_count'], 'visibility': visibility}


@app.route('/t/<code>/edit/api/enable', methods=['GET', 'POST'])
def t_edit_api_enable(code):
    code = sanitize_input(code)
    user_data = get_user_data(flask.session['username'])
    try:
        with open('../data/test_metadata/' + code + '.json') as f:
            data = parse_dict(f.read())
    except FileNotFoundError:
        return flask.render_template('404.html'), 404
    if data['owner'] == flask.session['username'] or 'admin' in user_data['tags'] or 'team' in user_data['tags'] or check_sharing_perms(data, flask.session['username'])['edit'] == True:
        pass
    else:
        return flask.redirect('/t/' + code)
    with open('../data/test_metadata/' + code + '.json') as f:
        test_data = parse_dict(f.read())
    if flask.request.method == 'GET':
        enable = test_data.get('enable')
        if enable == None:
            enable = True
        return enable
    elif flask.request.method == 'POST':
        req_data = flask.request.json
        test_data['enable'] = req_data['enable']
        with open('../data/test_metadata/' + code + '.json', 'w') as f:
            f.write(json.dumps(test_data))
        return {'success': True}


@app.route('/t/<code>/edit/api/visibility', methods=['GET', 'POST'])
def t_edit_api_visibility(code):
    code = sanitize_input(code)
    user_data = get_user_data(flask.session['username'])
    try:
        with open('../data/test_metadata/' + code + '.json') as f:
            data = parse_dict(f.read())
    except FileNotFoundError:
        return flask.render_template('404.html'), 404
    if data['owner'] == flask.session['username'] or 'admin' in user_data['tags'] or 'team' in user_data['tags'] or check_sharing_perms(data, flask.session['username'])['edit'] == True:
        pass
    else:
        return flask.redirect('/t/' + code)
    with open('../data/test_data/' + code + '/config.json') as f:
        test_data = parse_dict(f.read())
    if flask.request.method == 'GET':
        return test_data['visibility']
    elif flask.request.method == 'POST':
        req_data = flask.request.json
        test_data['visibility'] = req_data['visibility']
        with open('../data/test_data/' + code + '/config.json', 'w') as f:
            f.write(json.dumps(test_data))
        return {'success': True}


@app.route('/t/<code>/edit/api/title', methods=['GET', 'POST'])
def t_edit_api_title(code):
    code = sanitize_input(code)
    user_data = get_user_data(flask.session['username'])
    try:
        with open('../data/test_metadata/' + code + '.json') as f:
            data = parse_dict(f.read())
    except FileNotFoundError:
        return flask.render_template('404.html'), 404
    if data['owner'] == flask.session['username'] or 'admin' in user_data['tags'] or 'team' in user_data['tags'] or check_sharing_perms(data, flask.session['username'])['edit'] == True:
        pass
    else:
        return flask.redirect('/t/' + code)
    with open('../data/test_data/' + code + '/config.json') as f:
        test_data = parse_dict(f.read())
    if flask.request.method == 'GET':
        return test_data['test_name']
    elif flask.request.method == 'POST':
        req_data = flask.request.json
        tags = []
        removal_tag_records = []
        for tag in test_data['tags']:
            if tag not in tags:
                removal_tag_records.append(tag)
        for tag in removal_tag_records:
            if tag.strip() == '':
                continue
            try:
                with open('../data/global_test_records/' + tag) as f:
                    fdata = parse_dict(f.read())
                try:
                    fdata.pop(code)
                except KeyError:
                    pass
            except FileNotFoundError:
                fdata = {}
            with open('../data/global_test_records/' + tag, 'w') as f:
                f.write(json.dumps(fdata))
        for tag in tags:
            try:
                with open('../data/global_test_records/' + tag) as f:
                    fdata = parse_dict(f.read())
            except FileNotFoundError:
                fdata = {}
            fdata[code] = ''
            with open('../data/global_test_records/' + tag, 'w') as f:
                f.write(json.dumps(fdata))
        test_data['test_name'] = req_data['title'].strip()
        with open('../data/test_data/' + code + '/config.json', 'w') as f:
            f.write(json.dumps(test_data))
        return {'success': True}


@app.route('/t/<code>/edit/api/subject', methods=['GET', 'POST'])
def t_edit_api_subject(code):
    code = sanitize_input(code)
    user_data = get_user_data(flask.session['username'])
    try:
        with open('../data/test_metadata/' + code + '.json') as f:
            data = parse_dict(f.read())
    except FileNotFoundError:
        return flask.render_template('404.html'), 404
    if data['owner'] == flask.session['username'] or 'admin' in user_data['tags'] or 'team' in user_data['tags'] or check_sharing_perms(data, flask.session['username'])['edit'] == True:
        pass
    else:
        return flask.redirect('/t/' + code)
    with open('../data/test_data/' + code + '/config.json') as f:
        test_data = parse_dict(f.read())
    if flask.request.method == 'GET':
        return test_data['test_name']
    elif flask.request.method == 'POST':
        req_data = flask.request.json
        test_data['subject'] = req_data['subject']
        with open('../data/test_data/' + code + '/config.json', 'w') as f:
            f.write(json.dumps(test_data))
        return {'success': True}


@app.route('/t/<code>/edit/api/tags', methods=['GET', 'POST'])
def t_edit_api_tags(code):
    code = sanitize_input(code)
    user_data = get_user_data(flask.session['username'])
    try:
        with open('../data/test_metadata/' + code + '.json') as f:
            data = parse_dict(f.read())
    except FileNotFoundError:
        return flask.render_template('404.html'), 404
    if data['owner'] == flask.session['username'] or 'admin' in user_data['tags'] or 'team' in user_data['tags'] or check_sharing_perms(data, flask.session['username'])['edit'] == True:
        pass
    else:
        return flask.redirect('/t/' + code)
    with open('../data/test_data/' + code + '/config.json') as f:
        test_data = parse_dict(f.read())
    if flask.request.method == 'GET':
        return test_data['test_name']
    elif flask.request.method == 'POST':
        req_data = flask.request.json
        tags_raw = sanitize_input(req_data['tags']).split(',')
        tags = []
        for tag in tags_raw:
            tag = tag.strip()
            if tag != "":
                tags.append(tag)
        validated_result = validate_test_data_raw(test_data)
        if validated_result['success'] == True:
            if test_data.get('visible') == True or test_data.get('visible') == None:
                if 'teacher' in user_data['tags'] or 'team' in user_data['tags'] or 'admin' in user_data['tags']:
                    removal_tag_records = []
                    for tag in test_data['tags']:
                        if tag not in tags:
                            removal_tag_records.append(tag)
                    for tag in removal_tag_records:
                        if tag.strip() == '':
                            continue
                        try:
                            with open('../data/global_test_records/' + tag) as f:
                                fdata = parse_dict(f.read())
                            try:
                                fdata.pop(code)
                            except KeyError:
                                pass
                        except FileNotFoundError:
                            fdata = {}
                        with open('../data/global_test_records/' + tag, 'w') as f:
                            f.write(json.dumps(fdata))
                    for tag in tags:
                        try:
                            with open('../data/global_test_records/' + tag) as f:
                                fdata = parse_dict(f.read())
                        except FileNotFoundError:
                            fdata = {}
                        fdata[code] = ''
                        with open('../data/global_test_records/' + tag, 'w') as f:
                            f.write(json.dumps(fdata))
        test_data['tags'] = tags
        with open('../data/test_data/' + code + '/config.json', 'w') as f:
            f.write(json.dumps(test_data))
        return {'success': True}


@app.route('/t/<code>/edit/api/total_questions', methods=['GET', 'POST'])
def t_edit_api_total_questions(code):
    code = sanitize_input(code)
    user_data = get_user_data(flask.session['username'])
    try:
        with open('../data/test_metadata/' + code + '.json') as f:
            data = parse_dict(f.read())
    except FileNotFoundError:
        return flask.render_template('404.html'), 404
    if data['owner'] == flask.session['username'] or 'admin' in user_data['tags'] or 'team' in user_data['tags'] or check_sharing_perms(data, flask.session['username'])['edit'] == True:
        pass
    else:
        return flask.redirect('/t/' + code)
    with open('../data/test_data/' + code + '/config.json') as f:
        test_data = parse_dict(f.read())
    if flask.request.method == 'GET':
        return test_data['test_name']
    elif flask.request.method == 'POST':
        req_data = flask.request.json
        question_count = int(req_data['total_questions'])
        test_data['question_count'] = question_count
        with open('../data/t_editor_data/' + code + '.json') as f:
            editor_data = parse_dict(f.read())
        if question_count > len(editor_data.keys()):
            return {'success': False, "message": "Total question limit exceeding the number of available questions"}
        if question_count < 3:
            return {'success': False, "message": "Question limit should be a minimum of 3"}
        with open('../data/test_data/' + code + '/config.json', 'w') as f:
            f.write(json.dumps(test_data))
        return {'success': True}


@app.route('/t/<code>/edit/api/apply_changes', methods=['POST'])
def t_edit_api_apply_changes(code):
    code = sanitize_input(code)
    user_data = get_user_data(flask.session['username'])
    try:
        with open('../data/test_metadata/' + code + '.json') as f:
            data = parse_dict(f.read())
    except FileNotFoundError:
        return flask.render_template('404.html'), 404
    if data['owner'] == flask.session['username'] or 'admin' in user_data['tags'] or 'team' in user_data['tags'] or check_sharing_perms(data, flask.session['username'])['edit'] == True:
        pass
    else:
        return flask.redirect('/t/' + code)
    try:
        with open('../data/test_data/' + code + '/config.json') as f:
            test_data = parse_dict(f.read())
    except SyntaxError:
        test_data = {"test_name": "", "subject": "",
                     "tags": [], "question_count": 0, "visibility": True}
    try:
        with open('../data/t_editor_data/' + code + '.json') as f:
            editor_data_raw = parse_dict(f.read())
        editor_data = {"easy": [], "medium": [], "hard": []}
        for div in editor_data_raw:
            question = editor_data_raw[div]
            if question['difficulty'] == 'mid':
                question['difficulty'] = 'medium'
            for i, option in enumerate(question['options']):
                question['options'][i] = option.strip()
            editor_data[question['difficulty']].append({'question': question['question'].strip(
            ), 'answers': question['options'], 'correct_answer_index': question['c_a_i'], 'image': question.get('image')})
        if len(editor_data['easy']) == 0:
            return 'Missing 1 mark questions'
        if len(editor_data['medium']) == 0:
            return 'Missing 3 mark questions'
        if len(editor_data['hard']) == 0:
            return 'Missing 5 mark questions'
        for q in editor_data['easy']:
            if q['question'] == '':
                return 'Missing question text in a 1 mark question'
            for o in q['answers']:
                if o == '':
                    return 'Missing option text in a 1 mark question'
        for q in editor_data['medium']:
            if q['question'] == '':
                return 'Missing question text in a 3 mark question'
            for o in q['answers']:
                if o == '':
                    return 'Missing option text in a 3 mark question'
        for q in editor_data['hard']:
            if q['question'] == '':
                return 'Missing question text in a 5 mark question'
            for o in q['answers']:
                if o == '':
                    return 'Missing option text in a 5 mark question'
        with open('../data/test_data/' + code + '/config.json') as f:
            test_data = parse_dict(f.read())
        if len(editor_data['easy']) + len(editor_data['medium']) + len(editor_data['hard']) < test_data['question_count']:
            test_data['question_count'] = len(
                editor_data['easy']) + len(editor_data['medium']) + len(editor_data['hard'])
        if test_data['test_name'].strip() == "":
            return "Title empty. Please enter the title."
        if test_data['subject'].strip() == "":
            return "Subject empty. Please enter the subject."
        if test_data['tags'] == []:
            return "Student tags empty. Please enter the tags in comma-separated format."
        test_data['questions'] = editor_data
        with open('../data/test_data/' + code + '/config.json', 'w') as f:
            f.write(json.dumps(test_data))
        if test_data.get('visibility') == False:
            if 'teacher' in user_data['tags'] or 'team' in user_data['tags'] or 'admin' in user_data['tags']:
                tags = []
                removal_tag_records = []
                for tag in test_data['tags']:
                    if tag not in tags:
                        removal_tag_records.append(tag)
                for tag in removal_tag_records:
                    if tag.strip() == '':
                        continue
                    try:
                        with open('../data/global_test_records/' + tag) as f:
                            fdata = parse_dict(f.read())
                        try:
                            fdata.pop(code)
                        except KeyError:
                            pass
                    except FileNotFoundError:
                        fdata = {}
                    with open('../data/global_test_records/' + tag, 'w') as f:
                        f.write(json.dumps(fdata))
                for tag in tags:
                    try:
                        with open('../data/global_test_records/' + tag) as f:
                            fdata = parse_dict(f.read())
                    except FileNotFoundError:
                        fdata = {}
                    fdata[code] = ''
                    with open('../data/global_test_records/' + tag, 'w') as f:
                        f.write(json.dumps(fdata))
        with open('../data/test_metadata/' + code + '.json') as f:
            metadata = parse_dict(f.read())
        with open('../data/test_metadata/' + code + '.json', 'w') as f:
            dt = curr_dt()
            c_time = str(dt.hour) + ':' + str(dt.minute) + ':' + str(dt.second)
            c_date = str(dt.year) + '-' + str(dt.month) + '-' + str(dt.day)
            metadata['last_time'] = c_time
            metadata['last_date'] = c_date
            f.write(json.dumps(metadata))
        try:
            with open('../data/user_data/' + flask.session['username'] + '/created_tests/' + code + '.json') as f:
                cr_fdata = parse_dict(f.read())
            try:
                with open('../data/response_data/' + code + '.json') as g:
                    responses_count = len(parse_dict(g.read())['responses'])
            except FileNotFoundError:
                responses_count = 0
            with open('../data/user_data/' + flask.session['username'] + '/created_tests/' + code + '.json', 'w') as f:
                cr_fdata['name'] = test_data['test_name']
                cr_fdata['subject'] = test_data['subject']
                cr_fdata['responses_count'] = responses_count
                cr_fdata['last_time'] = c_time
                cr_fdata['last_date'] = c_date
                f.write(json.dumps(cr_fdata))
        except FileNotFoundError:
            with open('../data/user_data/' + flask.session['username'] + '/created_tests/' + code + '.json', 'w') as f:
                f.write(json.dumps({"last_time": c_time, "last_date": c_date,
                        "name": "Undefined", "subject": "Undefined", "responses_count": 0}))
        return 'ok'
    except FileNotFoundError:
        return "Missing questions. Add few questions and try again."


@app.route('/t/<code>/edit/editor/add_que', methods=['POST'])
def test_editor_add_que(code):
    code = sanitize_input(code)
    user_data = get_user_data(flask.session['username'])
    try:
        with open('../data/test_metadata/' + code + '.json') as f:
            data = parse_dict(f.read())
    except FileNotFoundError:
        return flask.render_template('404.html'), 404
    if data['owner'] == flask.session['username'] or 'admin' in user_data['tags'] or 'team' in user_data['tags'] or check_sharing_perms(data, flask.session['username'])['edit'] == True:
        pass
    else:
        return flask.redirect('/t/' + code)
    data = flask.request.json
    try:
        with open('../data/t_editor_data/' + code + '.json') as f:
            fdata = parse_dict(f.read())
    except FileNotFoundError:
        fdata = {}
    difficulty = data['difficulty']
    question = data['question']
    options = data['options']
    c_a_i = data['c_a_i']
    while 1:
        div_id = id_generator(5)
        if div_id not in fdata.keys():
            break
    fdata[div_id] = {"difficulty": difficulty,
                     "question": question, "options": options, "c_a_i": c_a_i}
    with open('../data/t_editor_data/' + code + '.json', 'w') as f:
        f.write(json.dumps(fdata))
    return {"div_id": div_id, "difficulty": difficulty, "question": question, "options": options, "c_a_i": c_a_i}


@app.route('/t/<code>/edit/editor/update_que', methods=['POST'])
def test_editor_update_que(code):
    code = sanitize_input(code)
    user_data = get_user_data(flask.session['username'])
    try:
        with open('../data/test_metadata/' + code + '.json') as f:
            data = parse_dict(f.read())
    except FileNotFoundError:
        return flask.render_template('404.html'), 404
    if data['owner'] == flask.session['username'] or 'admin' in user_data['tags'] or 'team' in user_data['tags'] or check_sharing_perms(data, flask.session['username'])['edit'] == True:
        pass
    else:
        return flask.redirect('/t/' + code)
    data = flask.request.json
    try:
        with open('../data/t_editor_data/' + code + '.json') as f:
            fdata = parse_dict(f.read())
    except FileNotFoundError:
        fdata = {}
    div_id = data['div_id']
    question = data['q']
    options = data['options']
    c_a_i = data['c_a_i']
    try:
        fdata[div_id]
    except KeyError:
        fdata[div_id] = {"difficulty": "easy"}
    fdata[div_id]['question'] = question
    fdata[div_id]['options'] = options
    fdata[div_id]['c_a_i'] = c_a_i
    with open('../data/t_editor_data/' + code + '.json', 'w') as f:
        f.write(json.dumps(fdata))
    return {"div_id": div_id, "question": question, "options": options, "c_a_i": c_a_i}


@app.route('/t/<code>/edit/editor/delete_que', methods=['POST'])
def test_editor_delete_que(code):
    code = sanitize_input(code)
    user_data = get_user_data(flask.session['username'])
    try:
        with open('../data/test_metadata/' + code + '.json') as f:
            data = parse_dict(f.read())
    except FileNotFoundError:
        return flask.render_template('404.html'), 404
    if data['owner'] == flask.session['username'] or 'admin' in user_data['tags'] or 'team' in user_data['tags'] or check_sharing_perms(data, flask.session['username'])['edit'] == True:
        pass
    else:
        return flask.redirect('/t/' + code)
    data = flask.request.json
    try:
        with open('../data/t_editor_data/' + code + '.json') as f:
            fdata = parse_dict(f.read())
    except FileNotFoundError:
        fdata = {}
    div_id = data['div_id']
    fdata.pop(div_id)
    with open('../data/t_editor_data/' + code + '.json', 'w') as f:
        f.write(json.dumps(fdata))
    return {"div_id": div_id}


@app.route('/t/<code>/edit/editor/load_data')
def test_editor_load_data(code):
    code = sanitize_input(code)
    user_data = get_user_data(flask.session['username'])
    try:
        with open('../data/test_metadata/' + code + '.json') as f:
            data = parse_dict(f.read())
    except FileNotFoundError:
        return flask.render_template('404.html'), 404
    except SyntaxError:
        pass
    if data['owner'] == flask.session['username'] or 'admin' in user_data['tags'] or 'team' in user_data['tags'] or check_sharing_perms(data, flask.session['username'])['edit'] == True:
        pass
    else:
        return flask.redirect('/t/' + code)
    try:
        with open('../data/t_editor_data/' + code + '.json') as f:
            fdata = parse_dict(f.read())
    except FileNotFoundError:
        fdata = {}
    output = {"easy": [], "mid": [], "hard": []}
    for div in fdata:
        output[fdata[div]['difficulty']].append({'q': fdata[div]['question'], 'options': fdata[div]
                                                ['options'], 'c_a_i': fdata[div]['c_a_i'], 'div_id': div, "image": fdata[div].get("image")})
    return output

#################### Error Handlers ####################


@app.errorhandler(404)
def e_404(e):
    return flask.render_template('404.html'), 404


@app.errorhandler(500)
def e_500(e):
    flask.session['error_referrer'] = flask.request.path
    return flask.render_template('500.html'), 500

#################### Other Endpoints ####################


@app.route('/gauthtoken', methods=["POST"])
def gauthtoken():
    data = flask.request.form
    id_token = data['idtoken']
    user_data = googleapis.verify_idtoken(id_token)
    if user_data == False:
        return "UNAUTHORIZED"
    try:
        with open("../data/google_sso/" + user_data['email']) as f:
            username = f.read().strip()
        username_user_data = get_user_data(username)
        if username_user_data.get('has_changed_password') == False:
            return "NEEDS_PASSWORD"
        if username_user_data == False:
            return "BAD_ACCOUNT"
        flask.session['username'] = username
        flask.session['perm_auth_key'] = hashlib.sha256(
            username_user_data['password'].encode()).hexdigest()
        return 'AUTHORIZED'
    except FileNotFoundError:
        return "BAD_ACCOUNT"


@app.route('/robots.txt')
def robots_txt():
    return '''
    User-agent: *
    Allow: /
    '''


@app.route('/privacy-policy')
def privacy_policy():
    return flask.render_template('privacy-policy.html')


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


if __name__ == '__main__':
    app.run(debug=True, port=80, host='0.0.0.0', threaded=True)
