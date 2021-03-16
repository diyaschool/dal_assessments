import textwrap
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

DOMAINS = ['localhost', 'diyaassessments.pythonanywhere.com', 'chaitanyapy.ml']
DOMAIN = 'diyaassessments.pythonanywhere.com'

gauth = sheets_api.authorize()

anonymous_urls = ['/favicon.ico', '/clear_test_cookies', '/logo.png', '/background.png', '/loading.gif', '/update_server']
mobile_agents = ['Android', 'iPhone', 'iPod touch']

client_req_times = {}

from_zone = tz.tzlocal()
to_zone = tz.gettz('Asia/Kolkata')

#################### Utility Functions ####################

def check_hook_integrity(ip):
    if ipaddress.ip_address(ip) in ipaddress.ip_network('192.30.252.0/22') or ipaddress.ip_address(ip) in ipaddress.ip_network('185.199.108.0/22') or ipaddress.ip_address(ip) in ipaddress.ip_network('140.82.112.0/20'):
        return True
    else:
        return False

def get_user_response(username, test_id):
    try:
        with open('../data/response_data/'+test_id+'.json') as f:
            data = ast.literal_eval(f.read())
    except FileNotFoundError:
        return False
    for i, response in enumerate(data['responses']):
        if response['username'] == username:
            return str(i)
    return False

def save_test_response(username, test_id):
    with open('../data/user_data/'+username+'/test_data/'+test_id+'.json') as f:
        tdata = ast.literal_eval(f.read())
    tdata['completed'] = True
    with open('../data/user_data/'+username+'/test_data/'+test_id+'.json', 'w') as f:
        f.write(str(tdata))
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
        data['question_stream'] = ast.literal_eval(f.read())['question_stream']
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
        test_metadata = ast.literal_eval(f.read())
    data["time_stamp"] = str(hour)+":"+str(minute)+":"+str(now.second)+' '+c_m
    data["long_time_stamp"] = str(now.day)+"-"+str(now.month)+"-"+str(now.year)+" "+str(hour)+":"+str(minute)+":"+str(now.second)+' '+c_m
    response_id = get_user_response(username, test_id)
    if response_id != False:
        print('response_id', response_id)
        with open('../data/response_data/'+test_id+'.json') as f:
            cdata = ast.literal_eval(f.read())
        cresponse_count = len(cdata['responses'])
        data['index'] = int(response_id)+1
        try:
            data['attempts'] = cdata['responses'][int(response_id)]['attempts'] + 1
        except KeyError:
            data['attempts'] = 2
        cdata['responses'][int(response_id)] = data
        with open('../data/response_data/'+test_id+'.json', 'w') as f:
            f.write(str(cdata))
    else:
        try:
            with open('../data/response_data/'+test_id+'.json') as f:
                cdata = ast.literal_eval(f.read())
            cresponse_count = len(cdata['responses'])
            with open('../data/user_data/'+test_metadata['owner']+'/created_tests/'+test_id+'.json') as f:
                cr_fdata = ast.literal_eval(f.read())
            cr_fdata['responses_count'] = len(cdata['responses'])+1
            with open('../data/user_data/'+test_metadata['owner']+'/created_tests/'+test_id+'.json', 'w') as f:
                f.write(str(cr_fdata))
            data['index'] = cresponse_count+1
            data['attempts'] = 1
            cdata['responses'].append(data)
            with open('../data/response_data/'+test_id+'.json', 'w') as f:
                f.write(str(cdata))
        except FileNotFoundError:
            with open('../data/user_data/'+test_metadata['owner']+'/created_tests/'+test_id+'.json') as f:
                cr_fdata = ast.literal_eval(f.read())
            cr_fdata['responses_count'] = 1
            with open('../data/user_data/'+test_metadata['owner']+'/created_tests/'+test_id+'.json', 'w') as f:
                f.write(str(cr_fdata))
            cdata = {}
            cdata['responses'] = []
            data['index'] = 1
            data['attempts'] = 1
            cdata['responses'].append(data)
            with open('../data/response_data/'+test_id+'.json', 'w') as f:
                f.write(str(cdata))

def delete_score(username, test_id):
    try:
        os.remove('../data/user_data/'+username+'/test_data/'+test_id+'.json')
    except FileNotFoundError:
        pass

def update_score(username, test_id, ans_res, difficulty, question_id, answer_index, score, ans_score, time_taken):
    try:
        with open('../data/user_data/'+username+'/test_data/'+test_id+'.json') as f:
            fdata = f.read()
        data = ast.literal_eval(fdata)
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
        f.write(str(data))
    return True

def get_user_data(user_id):
    try:
        with open('../data/user_metadata/'+user_id) as f:
            fdata = f.read()
        data = ast.literal_eval(fdata)
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
            c_a_i = ast.literal_eval(sheet[4][i])-1
            if sheet[5][i] == '':
                output['questions']['easy'].append({"question": sheet[2][i], "answers": sheet[3][i].split('\n'), "correct_answer_index": c_a_i})
            else:
                output['questions']['easy'].append({"question": sheet[2][i], "answers": sheet[3][i].split('\n'), "correct_answer_index": c_a_i, "image": sheet[5][i]})
        for i in range(len(sheet[6])):
            if sheet[6][i] == '':
                continue
            c_a_i = ast.literal_eval(sheet[8][i])-1
            if sheet[9][i] == '':
                output['questions']['medium'].append({"question": sheet[6][i], "answers": sheet[7][i].split('\n'), "correct_answer_index": c_a_i})
            else:
                output['questions']['medium'].append({"question": sheet[6][i], "answers": sheet[7][i].split('\n'), "correct_answer_index": c_a_i, "image": sheet[9][i]})
        for i in range(len(sheet[10])):
            if sheet[10][i] == '':
                continue
            c_a_i = ast.literal_eval(sheet[12][i])-1
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
                output['question_count'] = ast.literal_eval(sheet[0][2])
        except:
            q_n = 0
            for difficulty in output['questions']:
                for _ in output['questions'][difficulty]:
                    q_n += 1
            output['question_count'] = q_n
        return output
    except:
        return 'ERROR'

def create_new_test_sheet(owner):
    dt = datetime.datetime.now()
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
    sheet_id = sheets_api.create_sheet(test_id, gauth.load_credentials())
    os.mkdir('../data/test_data/'+test_id)
    os.mkdir('../data/test_data/'+test_id+'/files')
    with open('../data/test_data/'+test_id+'/config.json', 'w') as f:
        f.write('')
    with open('../data/test_metadata/'+test_id+'.json', 'w') as f:
        f.write(str({"owner": owner, "time": c_time, "date": c_date, "sheet_id": sheet_id, "last_time": c_time, "last_date": c_date}))
    with open('../data/user_data/'+owner+'/created_tests/'+test_id+'.json', 'w') as f:
        f.write(str({"last_time": c_time, "last_date": c_date, "name": "Undefined", "subject": "Undefined", "responses_count": 0}))
    return (test_id, sheet_id)

def validate_test_data(data_string):
    try:
        data = ast.literal_eval(data_string)
        if not isinstance(data['test_name'], str):
            return 'TEST_NAME_INVALID'
        if not isinstance(data['subject'], str):
            return 'SUBJECT_INVALID'
        if not isinstance(data['tags'], list):
            return 'TAGS_INVALID'
        if not isinstance(data['questions'], dict):
            return 'QUESTIONS_INAVLID'
        for question in data['questions']['easy']:
            if not isinstance(question['question'], str):
                return 'EASY_QUESTION_TEXT_INVALID'
            try:
                for answer in question['answers']:
                    if not isinstance(answer, str):
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
                    return 'EASY_IMAGE_URL_INVALID'
            except KeyError:
                pass
        for question in data['questions']['medium']:
            if not isinstance(question['question'], str):
                return 'MEDIUM_QUESTION_TEXT_INVALID'
            try:
                for answer in question['answers']:
                    if not isinstance(answer, str):
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
                    return 'MEDIUM_IMAGE_URL_INVALID'
            except KeyError:
                pass
        for question in data['questions']['hard']:
            if not isinstance(question['question'], str):
                return 'HARD_QUESTION_TEXT_INVALID'
            try:
                for answer in question['answers']:
                    if not isinstance(answer, str):
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
                    return 'HARD_IMAGE_URL_INVALID'
            except KeyError:
                pass
        return True
    except:
        return 'SYNTAX_INVALID'

def id_generator(size=10, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))

def load_questions(test_id):
    try:
        with open('../data/test_data/'+test_id+'/config.json') as f:
            fdata = f.read()
    except FileNotFoundError:
        return False
    data = ast.literal_eval(fdata)
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

#################### Reqeust Handlers ####################

@app.before_request
def before_request():
    try:
        prev_time = client_req_times[flask.request.remote_addr]
    except KeyError:
        prev_time = None
    if flask.request.headers['Host'] not in DOMAINS:
        return flask.redirect('http://'+DOMAIN+flask.request.path, 301)
    if flask.request.path != '/login' and flask.request.path not in anonymous_urls and 'static' not in flask.request.path:
        try:
            username = flask.session['username']
            f = open('../data/user_metadata/'+username)
            f.close()
        except KeyError:
            flask.session['login_ref'] = flask.request.path
            return flask.redirect('/login')
        except FileNotFoundError:
            flask.session['login_ref'] = flask.request.path
            return flask.redirect('/login')
        user_data = get_user_data(flask.session['username'])
        if user_data.get('has_changed_password') != None and flask.request.path != '/change_password':
            return flask.redirect('/change_password')

@app.after_request
def after_request(response):
    response.headers["Server"] = "DAL-Server/0.9"
    response.headers["Developers"] = "Chaitanya, Harsha, Kushal, Piyush"
    response.headers["Origin-School"] = "Diya Academy of Learning"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

#################### Content Endpoints ####################

@app.route('/')
def home():
    desktop = True
    for agent in mobile_agents:
        if agent in flask.request.headers['User-Agent']:
            desktop = False
    user_data = get_user_data(flask.session['username'])
    if desktop:
        return flask.render_template('home.html', username=flask.session['username'], name=user_data['name'])
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
        flask.session['t']['score'] = str(ast.literal_eval(flask.session['t']['score'])+ans_score)
    else:
        ans_score = 0
    flask.session['t']['verified'] = True
    time_taken = time.time()-flask.session['t']['time']
    update_score(flask.session['username'], code, flask.session['t']['prev_q_res'], flask.session['t']['difficulty'], flask.session['t']['q_id'], ast.literal_eval(data['answer']), flask.session['t']['score'], ans_score, time_taken)
    flask.session['t']['q'] = str(ast.literal_eval(flask.session['t']['q'])+1)
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
    for tag in user_data['tags']:
        if tag in question_data['tags'] or tag == 'admin' or tag == 'teacher' or tag == 'team' or code == 'demo':
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
    elif flask.request.args.get('skip') == '' and code == 'demo':
        flask.session['t']['c_q'] = [[0,1,2],[0,1,2],[0,1,2]]
        flask.session.modified = True
    if len(flask.session['t']['c_q'][0]) == len(question_data['questions']['easy']) and len(flask.session['t']['c_q'][1]) == len(question_data['questions']['medium']) and len(flask.session['t']['c_q'][2]) == len(question_data['questions']['hard']):
        score = flask.session['t']['score']
        flask.session.pop('t')
        flask.session.modified = True
        save_test_response(flask.session['username'], code)
        delete_score(flask.session['username'], code)
        return flask.render_template('t_completed.html', test_name=question_data['test_name'], score=score, name=user_data['name'], username=flask.session['username'], code=code)
    else:
        if question_data['question_count'] == ast.literal_eval(flask.session['t']['q'])-1:
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
                    f.write(str(user_data))
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
        if desktop:
            return flask.render_template('login.html', error=None, username='')
        else:
            return flask.render_template('mobile/login.html', error=None, username='')
    elif flask.request.method == 'POST':
        form_data = flask.request.form
        try:
            with open('../data/user_metadata/'+form_data['username'].lower()) as f:
                fdata = f.read()
            data = ast.literal_eval(fdata)
            password = hashlib.sha224(form_data['password'].encode()).hexdigest()
            if data['password'] != password:
                if desktop:
                    return flask.render_template('login.html', error='Invalid Credentials', username=form_data['username'])
                else:
                    return flask.render_template('mobile/login.html', error='Invalid Credentials', username=form_data['username'])
            else:
                flask.session['username'] = form_data['username'].lower()
                user_data = get_user_data(flask.session['username'])
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
    if 'admin' in user_data['tags'] or 'team' in user_data['tags']:
        pass
    else:
        return flask.render_template('401.html'), 401
    if flask.request.method == 'GET':
        return flask.render_template('new_test.html')
    else:
        test_data = create_new_test_sheet(flask.session['username'])
        test_id, _ = test_data
        return flask.redirect('/t/'+test_id+'/edit')

@app.route('/sheets_api_authorize', methods=['GET', 'POST'])
def sheets_api_authorize():
    user_data = get_user_data(flask.session['username'])
    if 'admin' in user_data['tags']:
        if flask.request.method == 'GET':
            creds = gauth.load_credentials()
            if creds:
                if gauth.verify_token(creds):
                    return 'authorized'
                else:
                    url = gauth.get_url()
                    return "<script>window.open('"+url+"')</script><form action='/sheets_api_authorize' method='POST'><input type='text' name='code' placeholder='code' autofocus><input type='submit' value='Enter'></form>"
            else:
                url = gauth.get_url()
                return "<script>window.open('"+url+"')</script><form action='/sheets_api_authorize' method='POST'><input type='text' name='code' placeholder='code' autofocus><input type='submit' value='Enter'></form>"
        else:
            data = flask.request.form
            creds = gauth.verify_code(data['code'])
            if creds != False:
                gauth.save_credentials(creds)
                return 'authorization_complete'
            else:
                return 'authorization_error'
    else:
        return flask.render_template('404.html'), 404

@app.route('/t/<code>/edit/', methods=['GET', 'POST'])
def test_edit(code):
    if '\\' in code or '.' in code:
        return flask.render_template('500.html'), 500
    user_data = get_user_data(flask.session['username'])
    try:
        with open('../data/test_metadata/'+code+'.json') as f:
            data = ast.literal_eval(f.read())
    except:
        return flask.render_template('404.html'), 404
    if data.get('owner'):
        if data['owner'] == flask.session['username'] or 'admin' in user_data['tags'] or 'team' in user_data['tags']:
            pass
        else:
            return flask.redirect('/t/'+code)
    else:
        if 'teacher' in user_data['tags'] or 'admin' in user_data['tags'] or 'team' in user_data['tags']:
            pass
        else:
            return flask.redirect('/t/'+code)
    with open('../data/test_data/'+code+'/config.json') as f:
        test_data = f.read()
    sheet_id = data.get('sheet_id')
    try:
        title = ast.literal_eval(test_data)['test_name']
    except:
        title = 'EDIT TEST'
    if flask.request.method == 'GET':
        sync_arg = flask.request.args.get('sync')
        if sync_arg == '':
            n_test_data = sheets_api.get_values(sheet_id, gauth.load_credentials())
            n_test_data = convert(n_test_data)
            if n_test_data == "ERROR":
                return flask.render_template('t_edit.html', test_data=test_data, sheet_id=sheet_id, title=title, username=flask.session['username'], name=user_data['name'], code=code, alert="Error during parsing spreadsheet", base_uri=flask.request.url_root)
            test_validation = validate_test_data(str(n_test_data))
            if test_validation == True:
                with open('../data/test_data/'+code+'/config.json', 'w') as f:
                    f.write(str(n_test_data))
                with open('../data/test_metadata/'+code+'.json') as f:
                    metadata = ast.literal_eval(f.read())
                with open('../data/test_metadata/'+code+'.json', 'w') as f:
                    dt = datetime.datetime.now()
                    c_time = str(dt.hour)+':'+str(dt.minute)+':'+str(dt.second)
                    c_date = str(dt.year)+'-'+str(dt.month)+'-'+str(dt.day)
                    metadata['last_time'] = c_time
                    metadata['last_date'] = c_date
                    f.write(str(metadata))
                try:
                    with open('../data/user_data/'+flask.session['username']+'/created_tests/'+code+'.json') as f:
                        cr_fdata = ast.literal_eval(f.read())
                    try:
                        with open('../data/response_data/'+code+'.json') as g:
                            responses_count = len(ast.literal_eval(g.read())['responses'])
                    except FileNotFoundError:
                        responses_count = 0
                    with open('../data/user_data/'+flask.session['username']+'/created_tests/'+code+'.json', 'w') as f:
                        cr_fdata['name'] = n_test_data['test_name']
                        cr_fdata['subject'] = n_test_data['subject']
                        cr_fdata['responses_count'] = responses_count
                        f.write(str(cr_fdata))
                except FileNotFoundError:
                    with open('../data/user_data/'+flask.session['username']+'/created_tests/'+code+'.json', 'w') as f:
                        f.write(str({"last_time": c_time, "last_date": c_date, "name": "Undefined", "subject": "Undefined", "responses_count": 0}))
                return flask.redirect('/t/'+code+'/edit')
            else:
                return flask.render_template('t_edit.html', test_data=test_data, sheet_id=sheet_id, title=title, username=flask.session['username'], name=user_data['name'], code=code, alert="Error: "+test_validation, base_uri=flask.request.url_root)
        else:
            return flask.render_template('t_edit.html', test_data=test_data, sheet_id=sheet_id, title=title, username=flask.session['username'], name=user_data['name'], code=code, alert=None, base_uri=flask.request.url_root)
    else:
        data = flask.request.form
        v_output = validate_test_data(data['test_data'])
        if v_output == True:
            with open('../data/test_data/'+code+'/config.json', 'w') as f:
                f.write(data['test_data'])
            return flask.render_template('t_edit.html', test_data=data['test_data'], sheet_id=sheet_id, title=title, username=flask.session['username'], name=user_data['name'], code=code, alert='Test updated', base_uri=flask.request.url_root)
        else:
            return flask.render_template('t_edit.html', test_data=data['test_data'], sheet_id=sheet_id, title=title, username=flask.session['username'], name=user_data['name'], code=code, alert='Error: '+v_output, base_uri=flask.request.url_root)

@app.route('/t/<code>/analytics/')
def test_analytics(code):
    user_data = get_user_data(flask.session['username'])
    try:
        with open('../data/test_metadata/'+code+'.json') as f:
            data = ast.literal_eval(f.read())
    except:
        return flask.render_template('404.html'), 404
    if data.get('owner'):
        if data['owner'] == flask.session['username'] or 'admin' in user_data['tags'] or 'team' in user_data['tags']  or 'teacher' in user_data['tags']:
            pass
        else:
            if 'teacher' in user_data['tags']:
                return flask.render_template('401.html'), 401
            else:
                return flask.redirect('/t/'+code)
    else:
        if 'teacher' in user_data['tags'] or 'admin' in user_data['tags'] or 'team' in user_data['tags'] or 'teacher' in user_data['tags']:
            pass
        else:
            return flask.redirect('/t/'+code)
    with open('../data/test_data/'+code+'/config.json') as f:
        test_data = f.read()
    try:
        title = ast.literal_eval(test_data)['test_name']
    except KeyError:
        title = 'TEST FAILING'
    try:
        with open('../data/response_data/'+code+'.json') as f:
            response_data = ast.literal_eval(f.read())
    except FileNotFoundError:
        response_data = {'responses': []}
    for response in response_data:
        try:
            response['attempts']
            attempts = True
        except:
            attempts = False
    return flask.render_template('test_analytics.html', test_name=title, username=flask.session['username'], name=user_data['name'], responses=response_data['responses'], response_count=len(response_data['responses']), code=code, attempts_bool=attempts)

@app.route('/t/<code>/analytics/<username>/')
def test_analytics_user(code, username):
    auserdata = get_user_data(username)
    user_data = get_user_data(flask.session['username'])
    try:
        with open('../data/test_metadata/'+code+'.json') as f:
            data = ast.literal_eval(f.read())
    except:
        return flask.render_template('404.html'), 404
    if data.get('owner'):
        if data['owner'] != flask.session['username']:
            if username != flask.session['username']:
                if 'teacher' in user_data['tags']:
                    return flask.render_template('401.html'), 401
                else:
                    return flask.redirect('/t/'+code)
    else:
        if 'teacher' in user_data['tags'] or 'admin' in user_data['tags'] or 'team' in user_data['tags']:
            pass
        else:
            return flask.redirect('/t/'+code)
    with open('../data/test_data/'+code+'/config.json') as f:
        test_data = f.read()
    try:
        title = ast.literal_eval(test_data)['test_name']
    except KeyError:
        title = 'TEST FAILING'
    with open('../data/response_data/'+code+'.json') as f:
        fdata = ast.literal_eval(f.read())['responses'][int(get_user_response(username, code))]
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

@app.route('/sheets_api_authorize/delete')
def sheets_api_authorize_delete():
    user_data = get_user_data(flask.session['username'])
    if  'admin' in user_data['tags']:
        try:
            os.remove('../data/credentials.pickle')
            return flask.redirect('/sheets_api_authorize')
        except:
            return 'file_not_found'
    else:
        return flask.render_template('404.html'), 404

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

@app.route('/upload_file')
def u_r():
    return flask.render_template('u_r.html')

@app.route('/t/<code>/upload/', methods=['GET', 'POST'])
def upload_file(code):
    if flask.request.method == 'GET':
        user_data = get_user_data(flask.session['username'])
        with open('../data/test_metadata/'+code+'.json') as f:
            test_metadata = ast.literal_eval(f.read())
        if flask.session['username'] != test_metadata['owner']:
            if 'admin' not in user_data['tags'] or 'team' not in user_data['tags'] or 'teacher' not in user_data['tags']:
                return flask.redirect('/t/'+code+'/')
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

@app.route('/t/<code>/upload/delete/<file_id>/')
def upload_delete(code, file_id):
    shutil.rmtree('../data/test_data/'+code+'/files/'+file_id+'/')
    return flask.redirect('/t/'+code+'/upload/')

@app.route('/t/<code>/static/<file_code>/')
def t_static(code, file_code):
    return flask.send_file('../data/test_data/'+code+'/files/'+file_code+'/'+[f for f in os.listdir('../data/test_data/'+code+'/files/'+file_code) if os.path.isfile(os.path.join('../data/test_data/'+code+'/files/'+file_code, f))][0])

@app.route('/robots.txt')
def robot_txt():
    return 'Telegram: @ChaitanyaPy, Github: https://github.com/ChaitanyaPy/'

#################### Error Handlers ####################

@app.errorhandler(404)
def e_404(e):
    return flask.render_template('404.html'), 404

@app.errorhandler(500)
def e_500(e):
    flask.session['error_referrer'] = flask.request.path
    return flask.render_template('500.html'), 500

#################### Other Endpoints ####################

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

if __name__=='__main__':
    app.run(debug=True , port=80, host='0.0.0.0', threaded=True)
