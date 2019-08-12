from flask import request
from pymongo import MongoClient
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from jenkinsapi.utils.crumb_requester import CrumbRequester
import random,requests,json
import smtplib
import configparser
from jenkinsapi.jenkins import Jenkins

key = 'abcdefghijklmnopqrstuvwxyz'
offset = 5
jenkins_username = ""
jenkins_token = ""
jenkins_url = ""
config = configparser.ConfigParser()

def loadjenkins():
    config.read("config.ini")
    global server,crumb,jenkins_username,jenkins_token,jenkins_url
    jenkins_username=config.get("JENKINSPARAMETER", "username")
    jenkins_token=config.get("JENKINSPARAMETER", "token")
    jenkins_url=config.get("JENKINSPARAMETER", "jenkins_url")
    crumb = CrumbRequester(username=jenkins_username, password=jenkins_token, baseurl=jenkins_url)
    server = Jenkins(jenkins_url, username=jenkins_username, password=jenkins_token, requester=crumb, timeout=10)

def registerjob(jobname):
    joburl=''
    config.read("config.ini")
    user_list = requests.get(config.get("SLACKPARAMETER", "slack_user_list"))

    for item in server._data['jobs']:
        if item['name'] == jobname:
            joburl=item['url']
            break
    if joburl == '':
        responsetext="*"+jobname+" * No such job found on Jenkins Server"
    else:
        indexvalue = joburl.index('//', )
        jenkins_json_url = joburl[:indexvalue + 2] + jenkins_username+':'+jenkins_token+'@' + joburl[indexvalue + 2:]+'/api/json'
        paralist=requests.get(url=jenkins_json_url)
        paralist=json.loads(paralist.text)['actions'][0]['parameterDefinitions']
        if len(paralist) <= 5:
            db = getdb_doclist()
            entities = {}
            for item in paralist:
                if item['type']=='StringParameterDefinition':
                    entities[item['name']]={'value':item['defaultParameterValue']['value'],'type':'text'}
                elif item['type']=='ChoiceParameterDefinition':
                    entities[item['name']] = {'value':','.join(item['choices']),'type': 'select','default': item['defaultParameterValue']['value']}
                elif item['type']=='BooleanParameterDefinition':
                    entities[item['name']] = {'value':'True,False','default': item['defaultParameterValue']['value'], 'type': 'select'}

            db.jenkins_job.insert({"name": jobname, "jobname": jobname,"value":{'url':+user_list+'/build','intent':'Fire Build'},"entities": entities})
            db.master.update_one({"master.key": "jenkins jobs: "},{"$set": {"master.value."+jobname: [jobname]}})
            responsetext="Jenkins Job Registered Successfully"
        else:
            responsetext="Job with less than or equal to 5 parameters are allowed"
    if responsetext == '':
        responsetext = "Something went wrong , please try after some time"

    return responsetext

def load_authentication():
    userslitst=getdb_doclist()
    for item in userslitst.master.find():
        if 'slackauth' in item['master']['key']:
            return item['master']['value']

def getdb_doclist():
    config.read("config.ini")
    connection = MongoClient(config.get("DBPARAMETER", "host"),int(config.get("DBPARAMETER", "port")))
    return connection.botengine

def gen_hex_colour_code():
   return ''.join([random.choice('0123456789ABCDEF') for x in range(6)])

def load_keys():
    doc_list = getdb_doclist()
    keylist=[]
    keys = []
    key_data=[]
    for item in doc_list.master.find():
        if item['master']['key'][0] == 'help':
            for key in item['master']['value']:
                keys.append(key)
                keylist.append({'title': key, 'short': 'true'})
    key_data.append(keys)
    key_data.append(keylist)

    return key_data

def authneeded(searchtext):
    doc_list = getdb_doclist()
    for item in doc_list.master.find():
        if searchtext.lower() in item['master']['key']:
            return (item['master']['auth'][item['master']['key'].index(searchtext.lower())])

def load_help():
    keylist = []
    doc_list = getdb_doclist()
    for item in doc_list.master.find():
        if item['master']['key'][0] == 'help':
            for k, v in item['master']['value'].items():
                keylist.append({'title': k, 'value': v, 'short': 'true'})
    return keylist

def load_db():
    #get the data of the search value
    data = {'query': request.form.get('text')}
    itemform = []
    config.read("config.ini")
    r = requests.post(config.get("SERVICEPARAMETER", "root_service"), data=data)
    messages = json.loads(r.text)

    for s in messages[0]:
        global searchText;
        if data['query'].lower() in s.lower():
            childform = {"type": "select"}
            childform['name'] = childform['text'] = "Select "+s.capitalize()
            itr = 0
            for item in messages[1]:
                childele = []
                for ele in messages[2][itr]:
                    childele.append({'text': ele, 'value': item + ';' + ele})
                itemform.append({'text': item, 'options': childele})
                itr = itr + 1
            childform['option_groups'] = itemform
            searchText= s.capitalize()
            pdict = {'Select' + searchText: [childform]}
    return pdict

def getemailid(username):
    emailid=''
    config.read("config.ini")
    try:
        res = requests.get(config.get("SLACKPARAMETER", "slack_user_list"))
        userlist = res.json()
    except ConnectionAbortedError:
        print("Unable to connect to server for user list")

    for item in userlist["members"]:
        if username in item['id'] and item["profile"]["email"]:
            emailid = item["profile"]["email"]
            break
    return emailid

def sendEmailRequest(userid):
    authlist = getdb_doclist()
    encryptedid = encrypt(offset, userid)
    for item in authlist.master.find():
        if item['master']['key'][0] == 'slackauth':
            adminuser=item['master']['value']["admin"]
            break

    config.read("config.ini")
    res = requests.get(config.get("SLACKPARAMETER", "slack_user_list"))
    from_email = config.get("MAILPARAMETERS", "from_email")
    userlist=res.json()
    for item in userlist["members"]:
        if userid in item['id']:
            realname=item["real_name"]
            email=item["profile"]["email"]
            break

    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'Approval Request for Slack Service'
    msg['From'] = from_email
    recipients = adminuser
    msg['To'] = ", ".join(recipients)

    text = MIMEText(realname+'('+email+')' + ' needs authorization for using Slack Service.<br><a href= '+config.get("SERVICEPARAMETER", "slack_service_url")+'/slack/adduser?authorize_user:'+encryptedid+'&auth:y>Approve</a>&nbsp;&nbsp;&nbsp;<a href= '+config.get("SERVICEPARAMETER", "slack_service_url")+'/slack/adduser?authorize_user:'+encryptedid+'&auth:n>Decline</a>', 'html')
    msg.attach(text)

    mail = smtplib.SMTP('smtp.gmail.com', 587)
    mail.starttls()
    mail.login(from_email, config.get("MAILPARAMETERS", "mail_password"))
    mail.sendmail(msg['From'], msg['To'], msg.as_string())
    mail.quit()

def getuserlist(user_dict):
    config.read("config.ini")
    res = requests.get(config.get("SLACKPARAMETER", "slack_user_list"))
    userlist = res.json()
    for item in userlist["members"]:
        if decrypt(offset, user_dict['authorize_user']).upper() in item['id']:
            realname = item["real_name"]
            emailid = item["profile"]["email"]
            break

    return emailid

def sendNotification(toemailid,msgcontent):

    config.read("config.ini")
    from_email = config.get("MAILPARAMETERS", "from_email")

    authlist = getdb_doclist()
    for item in authlist.master.find():
        if item['master']['key'][0] == 'slackauth':
            adminuser = item['master']['value']["admin"]
            break

    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'Approval Request for Slack Service'
    msg['From'] = from_email
    msg['To'] = toemailid
    recipients = adminuser
    msg['Cc'] = ", ".join(recipients)

    part1 = MIMEText(msgcontent, 'plain')
    msg.attach(part1)
    mail = smtplib.SMTP('smtp.gmail.com', 587)
    mail.starttls()
    mail.login(from_email, config.get("MAILPARAMETERS", "mail_password"))
    mail.sendmail(msg['From'], [msg['To'], msg['Cc']], msg.as_string())
    mail.quit()

def load_data(msgdata):
    testdict = {}
    textdata = ""
    attachmentsdata =[]
    if msgdata:
        for i in range(0, len(msgdata[0])):
            testdict['title'] = msgdata[0][i]
            for k, v in msgdata[1][i].items():
                if k == "data" and v is not None:
                    for k1, v1 in v.items():
                        if k1 == 'tabulardata':
                            for i in v1[1]:
                                textdata = textdata + '\n' + i[0]
                                if len(i) > 1:
                                    for itr in range(1,len(i)):
                                        textdata=textdata  + ' : ' + i[itr]
                        else:
                            textdata = textdata + '\n' + k1 + ' : ' + str(v1)
                elif v is None:
                    textdata="No Result"
            if textdata:

                if k1 == 'url':
                    testdict['text'] = "Click here to get "+testdict['title']
                    testdict['title_link'] = textdata.split("\nurl : ")[1]
                else:
                    testdict['text'] = textdata
                testdict['color'] = gen_hex_colour_code()
                attachmentsdata.append(testdict)
            testdict = {}
            textdata = ""

        return attachmentsdata

def encrypt(n, plaintext):
    """Encrypt the string and return the ciphertext"""
    result = ''

    for l in plaintext.lower():
        try:
            i = (key.index(l) + n) % 26
            result += key[i]
        except ValueError:
            result += l

    return result.lower()

def decrypt(n, ciphertext):
    """Decrypt the string and return the plaintext"""
    result = ''
    for l in ciphertext:
        try:
            i = (key.index(l) - n) % 26
            result += key[i]
        except ValueError:
            result += l

    return result
