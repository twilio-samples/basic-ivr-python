from flask import Flask, request, session
from twilio.twiml.voice_response import VoiceResponse, Say, Gather, Dial, Record, Enqueue

app = Flask(__name__)
app.config['SECRET_KEY'] = 'top-secret!'

def enter_greeting():
    return Say('Welcome to ACME, Inc.')

def enter_menu():
    gather = Gather(action_on_empty_result=True, num_digits=1)
    gather.say('Listen to the following menu options. '
               'For sales, press one. '
               'For support, press two. '
               'For our business hours, press three. '
               'To repeat these options, press nine. '
               'To speak with the receptionist, press zero.')
    return gather

def exit_menu():
    transitions = {
        '1': 'sales',
        '2': 'support',
        '3': 'hours',
        '9': 'menu',
        '0': 'reception',
    }
    selection = request.form.get('Digits')
    if selection in transitions:
        return enter_state(transitions[selection])
    else:
        return enter_state('error')

def enter_sales():
    return [
        Say('All our sales representatives are currently busy, please leave us a message and we will return your call as soon as possible.'),
        Record(),
    ]

def enter_support():
    return [
        Say('You are being transferred to the support line. A representative will be with you shortly.'),
        Enqueue('support'),
    ]

def enter_hours():
    gather = Gather(action_on_empty_result=True, num_digits=1)
    gather.say('We are open Mondays through Fridays from 9 AM to 6 PM.')
    gather.pause()
    gather.say('Press 1 to repeat this message or any other key to go back to the menu.')
    return gather

def exit_hours():
    selection = request.form.get('Digits')
    if selection == '1':
        return enter_state('hours')
    else:
        return enter_state('menu')


def enter_reception():
    return Dial('+19715701777')

def enter_error():
    return Say('The option that you selected is invalid.')

IVR = {
    'greeting': (enter_greeting, 'menu'),
    'menu': (enter_menu, exit_menu),
    'sales': (enter_sales, None),
    'support': (enter_support, None),
    'hours': (enter_hours, exit_hours),
    'reception': (enter_reception, None),
    'error': (enter_error, 'menu'),
}

def enter_state(state):
    response = VoiceResponse()
    while True:
        # access the requested state
        session['ivr_state'] = state
        enter_handler, exit_handler = IVR[state]

        # invoke the "enter" action for the state
        actions = enter_handler()
        if isinstance(actions, list):
            for action in actions:
                response.append(action)
        else:
            response.append(actions)

        # if the state has a string exit handler, transition to that state
        # and continue building a response
        if isinstance(exit_handler, str):
            state = exit_handler
        else:
            # let the called hear the response for this state and provide input
            return response

def exit_state(state):
    _, exit_handler = IVR[state]
    return exit_handler()

@app.route('/webhook', methods=['POST'])
def ivr_webhook():
    state = session.get('ivr_state')
    if state is None:
        # this is a new call
        return str(enter_state('greeting'))
    else:
        # we received input an the current state, so we can now exit it and
        # transition to a new state
        return str(exit_state(state))