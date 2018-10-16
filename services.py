from flask import Flask, make_response
from  builtins import any
from data_util import *
from slackclient import SlackClient
from flask import Markup

app = Flask(__name__)

keys=[]
messages = []
childele = []
searchText=""
jobdetails={}
configdata=[]
slack_auth=load_authentication()
slackconfig = configparser.ConfigParser()
slackconfig.read("config.ini")
filter_service=slackconfig.get("SERVICEPARAMETER", "root_service")+'/filter'
root_service=slackconfig.get("SERVICEPARAMETER", "root_service")+'/root'
slack_client = SlackClient(slackconfig.get("SLACKPARAMETER", "slack_bot_token"))
headers = {'content-type': 'application/json'}

if slackconfig.get("JENKINSPARAMETER", "username"):
    loadjenkins()

def post_msg_to_channel(channelid,attachments="",header_text=""):
    slack_client.api_call(
        "chat.postMessage",
        as_user=True,
        channel=channelid,
        text=header_text,
        attachments=attachments
    )

def update_channel_msg(channelid,timestamp,attachments,header_text=""):

    slack_client.api_call(
        "chat.update",
        as_user=True,
        channel=channelid,
        ts=timestamp,
        text=header_text,
        attachments=attachments
    )

def registernewjob(channelid,user_id):
    text= "Click here to register new jenkins job"
    actions= [
        {
            "type": "button",
            "name": "Register Job",
            "text": "Register Job 🛫",
            "value": "Yes",
            "style": "primary"
        }
    ]
    attachments = [{"text": "", "callback_id": user_id, "color": gen_hex_colour_code(), "attachment_type": "default",
                    "actions": actions}]
    post_msg_to_channel(channelid,attachments,text)

def sendauthmessage(channelid,username,timestamp=""):
    text= "Click here to send Authentication request"
    header_text = "Sorry, It seems that your are not a authorized User for this service."
    actions=[
        {
            "type": "button",
            "name": "Request for auth",
            "text": "Request 🛫",
            "value": "Yes",
            "style": "primary"
        }
    ]

    attachments = [{"text": text,"attachment_type": "default","callback_id": username,"color": gen_hex_colour_code(),"actions": actions}]
    if timestamp != "":
        update_channel_msg(channelid, timestamp, attachments, header_text)
    else:
        post_msg_to_channel(channelid, attachments, header_text)

def _load_data(text_data):
    #get the data of the search value
    data = {'query': text_data}
    itemform = []
    r = requests.post(root_service, data=data)
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

@app.route('/slack', methods=['POST'])
def inbound():
    print("inside slack")
    global messages
    user_id = request.form.get('user_id')
    channelid = request.form.get('channel_id')
    text = request.form.get('text')

    keys = load_keys()
    keyname=keys[1]

    emailid=getemailid(user_id)

    if text.lower() in  ['hi','hello']:

        header_text = "Hello \n I am SwiftOps Genie :genie:, So how may I assist you today?",
        attachments = [{"fields": keyname,"color": gen_hex_colour_code()}]
        post_msg_to_channel(channelid, attachments, header_text)

    elif text.lower() in  ['help']:
        keyname = load_help()
        header_text = "I am SwiftOps Genie, I\'m here to help you to get",
        attachments = [{"fields": keyname, "color": gen_hex_colour_code()}]
        post_msg_to_channel(channelid, attachments, header_text)

    elif len(text) < 4 and len(text)!=0:

        header_text = "Enter atleast four character  \n Suggestions",
        attachments = [{"fields": keyname, "color": gen_hex_colour_code()}]
        post_msg_to_channel(channelid, attachments, header_text)

    elif not any(text.lower() in x for x in keys[0]):
        header_text = "Your search - " +text + " did not match any keys\n Suggestions",
        attachments = [{"fields": keyname, "color": gen_hex_colour_code()}]
        post_msg_to_channel(channelid, attachments, header_text)

    elif len(text) != 0:
        for x in keys[0]:
            if text.lower() in x:
                slack_auth = load_authentication()
                if text.lower() in 'register' and emailid in slack_auth.get('AUTHOURISED_USERS'):
                    registernewjob(channelid,user_id)

                elif (authneeded(x) == 'yes' or text.lower() in 'register' or text.lower() in 'configuration' ) and emailid not in slack_auth.get('AUTHOURISED_USERS'):
                    sendauthmessage(channelid,user_id)

                elif text.lower() in 'configuration':
                    header_text = "Select the below option for config"
                    db = getdb_doclist().master
                    dbconflist = db.find({'name': 'configuration'})
                    finaldict = []
                    global configdata
                    for item in dbconflist:
                        configdata = item['master']['value']
                        for chitem in item['master']['value'][0].keys():
                            data = {'text': chitem, 'value': chitem}
                            finaldict.append(data)

                    attachments = [
                        {'text': '', 'color': gen_hex_colour_code(), 'callback_id': user_id, 'attachment_type': 'default',
                         'actions': [{'type': 'select', 'name': 'config', 'text': 'Select Option', 'options': finaldict}]}]
                    post_msg_to_channel(channelid, attachments, header_text)

                else:
                    messages = _load_data(text)
                    if messages.get("Select" + searchText)[0]['type']=='select' and len(messages.get("Select" + searchText)[0]['option_groups'][0]['options']) == 0:
                        attachments = [{"text": "No data found for this option", "color": gen_hex_colour_code(), "callback_id": user_id,
                                        "attachment_type": "default"}]
                        post_msg_to_channel(channelid, attachments)
                    else:
                        header_text = "Select the appropiate option!!!"
                        attachments = [{"text": "", "color": gen_hex_colour_code(),"callback_id": user_id,"attachment_type": "default",
                                        "actions": [messages.get("Select" + searchText)[0]]}]
                        post_msg_to_channel(channelid, attachments, header_text)

    return make_response("", 200)


@app.route("/slack/message_actions", methods=["POST"])
def message_actions():
    print("inside message action")
    global jobdetails
    # Parse the request payload
    message_action = json.loads(request.form.get("payload"))
    # print message_action
    user_id = message_action.get("user").get("id")
    username = message_action.get("user").get("name")
    channelid = message_action.get('channel').get('id')
    textresponse = ""
    attachmentsdata= ""
    if message_action["type"] == "interactive_message":
        actions = message_action["actions"]
        slack_auth = load_authentication()
        emailid = getemailid(user_id)
        if actions[0]["name"] == "Request for auth":
            if emailid in slack_auth.get('AUTHOURISED_USERS'):
                textresponse = "You are already a Authorised User"
            else:
                sendEmailRequest(user_id)
                textresponse="Your request has been submitted successfully.\n Admin will reply you soon, till then use other services."
            timestamp = message_action['original_message']['ts']
            attachments = [{
                "text": "",
                "callback_id": username,
                "color": gen_hex_colour_code(),
                "attachment_type": "default"
            }]
            update_channel_msg(channelid, timestamp, attachments, textresponse)

        elif actions[0]["name"].lower() == "config":
            global indexvalue
            jobdetails[user_id] = {}
            jobdetails[user_id]['ts'] = message_action['original_message']['ts']
            db = getdb_doclist().master
            dbconflist = db.find({'name': 'configuration'})
            for item in dbconflist:
                paralist=item['master']['value'][0][actions[0].get('selected_options')[0].get('value')].keys()
                jobdetails[user_id]['indexvalue'] = actions[0].get('selected_options')[0].get('value')
            configparameters=[]
            for itemlist in paralist:
                configparameters.append({'name': itemlist, 'type': 'text', 'label': itemlist})
            open_dialog = slack_client.api_call(
                "dialog.open",
                trigger_id=message_action["trigger_id"],
                dialog={
                    "title": "Enter Config Parameter",
                    "submit_label": "Submit",
                    "callback_id": user_id + "config",
                    "elements": configparameters
                }
            )

        elif actions[0]["name"] == "Register Job":
            if emailid not in slack_auth.get('AUTHOURISED_USERS'):
                sendauthmessage(channelid, user_id, message_action['original_message']['ts'])
            else:
                jobdetails[user_id] = {}
                jobdetails[user_id]['ts'] = message_action['original_message']['ts']
                open_dialog = slack_client.api_call(
                    "dialog.open",
                    trigger_id=message_action["trigger_id"],
                    dialog={
                        "title": "Enter Job Parameter",
                        "submit_label": "Submit",
                        "callback_id": user_id + "jenkins_job_form",
                        "elements": [{'name':'Job Name','type':'text','label':'Job Name'}]
                    }
                )
        else:
            for action in actions:
                actionSent = action["name"]
                data_info = action.get('selected_options')[0].get('value')
                if actionSent == 'Select Jenkins jobs :' and emailid not in slack_auth.get('AUTHOURISED_USERS'):
                    sendauthmessage(channelid, user_id,message_action['original_message']['ts'])

                elif actionSent == 'Select Jenkins jobs:' and emailid in slack_auth.get('AUTHOURISED_USERS'):
                    data = {'query': data_info, 'username': message_action.get('user').get('name')}
                    response = requests.post(filter_service, data=data)
                    jobdetails=json.loads(response.text)[1][0]
                    elementslist=[]
                    for key,value in jobdetails['entities'].items():
                        optionslist = []
                        dummy = {}
                        dummy["type"]="text"
                        dummy["label"]=key
                        dummy["name"]=key
                        if value['type'] == 'select':
                            dummy["type"] = "select"
                            for item in value['value'].split(','):
                                options = {}
                                options["label"]=item
                                options["value"] = item
                                optionslist.append(options)
                            options = {}
                            options["label"] = "default value :"+ str(jobdetails['entities'][key]['default'])
                            options["value"] = str(jobdetails['entities'][key]['default'])
                            optionslist.append(options)
                            dummy["options"]=optionslist
                        elementslist.append(dummy)

                    open_dialog = slack_client.api_call(
                        "dialog.open",
                        trigger_id=message_action["trigger_id"],
                        dialog={
                            "title": "Enter Job Parameter",
                            "submit_label": "Submit",
                            "callback_id": user_id + "jenkins_job_form",
                            "elements":elementslist
                        }
                    )
                    jobdetails[user_id] = {}
                    jobdetails[user_id]['jobname']=jobdetails['jobname']
                    jobdetails[user_id]['url']=jobdetails['value']['url']
                    jobdetails[user_id]['ts']=message_action['original_message']['ts']

                else:
                    try:
                        data = {'query': data_info, 'username':message_action.get('user').get('name')}
                        buildresponse = requests.post(filter_service, data=data)
                        msgdata = json.loads(buildresponse.text)
                        rel_build = data_info.split(';')
                        attachmentsdata=load_data(msgdata)

                        if ('jenkins' in rel_build[0]):
                            textresponse=rel_build[0]
                        elif ('build' in rel_build[0].lower()):
                            textresponse = "{} --- Release {}".format(rel_build[0].capitalize(), rel_build[1].capitalize())
                        else:
                            textresponse="Build {} --- Release {}".format(rel_build[1],rel_build[0].split(" ")[1])
                    except:
                        print("Unable to connect filter service")
                        textresponse=":notok: Something went wrong , please try after some time"

            slack_client.api_call(
                "chat.postMessage",
                as_user=True,
                channel=channelid,
                text=textresponse,
                attachments=attachmentsdata
            )

    elif message_action["type"] == "dialog_submission":
        jenkinsdata={}

        if 'Job Name' in message_action['submission']:
            db = getdb_doclist().jenkins_job
            job_cursor = db.find({'jobname': message_action['submission']['Job Name']})
            if job_cursor.count() >= 1:
                response = "Job Already Registered"
            else:
                response = registerjob(message_action['submission']['Job Name'])

        elif 'config' in message_action['callback_id']:
            global configdata
            db = getdb_doclist().master
            configdata[0][jobdetails[user_id]['indexvalue']]=message_action['submission']
            db.update({"name": "configuration"}, {'$set': {"master.value": configdata}})
            response = ":rocket: Configuration Updated !!!"
        else:
            jenkinsdata['data']={"parameter":"","jobname":""}
            jenkinsdata['data']['parameter']=message_action['submission']
            jenkinsdata['data']['jobname']=jobdetails[user_id]['jobname']
            resp = requests.post(jobdetails[user_id]['url'], data=json.dumps(jenkinsdata), headers=headers)
            if resp.text == 'Build fired':
                response="Build Initiated Successfully !!!"
            else:
                response = "Unable to Initiated Build"

        attachments = [{
            "text": response,
            "callback_id": user_id,
            "color": gen_hex_colour_code(),
            "attachment_type": "default"
        }]
        update_channel_msg(channelid, jobdetails[user_id]['ts'], attachments)

    return make_response("", 200)

@app.route("/slack/adduser", methods=["GET"])
def adduser():
    print("hello")
    slackconfig.read("config.ini")
    user_details=request.url.split('?')[1].split('&')
    user_dict={}
    for item in user_details:
        user_dict[item.split(':')[0]]=item.split(':')[1]
    email =getuserlist(user_dict)
    res = requests.get(slackconfig.get("SLACKPARAMETER", "slack_user_list"))
    userlist = res.json()

    for item in userlist["members"]:
        if decrypt(offset, user_dict['authorize_user']).upper() in item['id']:
            realname = item["real_name"]
            break

    if user_dict['auth'].lower() == 'y':

        db = getdb_doclist().master
        for item in db.find():
            if 'slackauth' in item['master']['key']:
                if email in item['master']['value']['AUTHOURISED_USERS']:
                    notimsg="User is already Authorized"
                    break
                else:
                    db.update({"name": "slackauth"}, {"$addToSet": {"master.value.AUTHOURISED_USERS": email}})
                    notimsg="User Authorized Successfully"
                    slack_client.api_call(
                        "chat.postMessage",
                        as_user=True,
                        channel=decrypt(offset, user_dict['authorize_user']).upper(),
                        text="Your authentication for swiftops service is approved by admin."
                    )
                    sendNotification(email,"Hi "+realname+",\n\nYour authentication for swiftops service is approved by admin.\n\nThanks and Regards,\nDevOps Admin")
    elif user_dict['auth'].lower() == 'n':
        notimsg = "User Decline Successfully"
        slack_client.api_call(
            "chat.postMessage",
            as_user=True,
            channel=decrypt(offset, user_dict['authorize_user']).upper(),
            text="Sorry, your authentication for swiftops service is not approved by admin.\nFor more info contact DevOps Team."
        )
        sendNotification(email, "Hi "+realname+",\n\nSorry, your authentication for swiftops service is not approved by admin.\nFor more info contact DevOps Team.\n\nThanks and Regards,\nDevOps Admin")

    return make_response(notimsg, 200)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, debug=True)
