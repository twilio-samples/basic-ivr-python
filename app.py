""" 
app.py
Description: The code you've provided is a Flask-based Interactive Voice Response (IVR) system that uses Twilio's Voice API. The system allows callers to interact with a phone menu and choose options to get transferred to sales, support, reception, or to hear business hours. 

 Contents:
1. Initialize the Flask application
2. Create helper functions
3. Handle hours of operation
4. State machine implementation 
5. Define the webhook

This code creates a dynamic voice menu system that directs callers to different options based on input and responds accordingly.
Each time a caller interacts with the IVR, the session keeps track of the current state (ivr_state) so the system knows how to handle 
subsequent requests.
"""

from flask import Flask, request, session
from twilio.twiml.voice_response import VoiceResponse, Say, Gather, Dial, Record, Enqueue

"""
1. Initialize the Flask application

"""
app = Flask(__name__)
app.config['SECRET_KEY'] = 'top-secret!'

"""
2. Create helper functions
The IVR defines specific functions to handle different states, such as sales, support, and reception.
Each method checks the user input and uses the built in Twilio functions such as Say, Gather, Record, Enqueue, and Dial to interact
with the user. 
"""

def enter_greeting():
    return Say('Welcome to ACME, Inc.')


"""
The "action_on_empty_result=True" parameter passed to Gather ensures that if the gather object times out before the user presses any key,
Twilio will keep the call connected and continue to invoke the application webhook. The default action when a gather timeout occurs 
is to end the call, which does not work well for this application. The num_digits argument tells Twilio that the user needs to key in a single digit.
"""
def enter_menu():
    gather = Gather(action_on_empty_result=True, num_digits=1)
    gather.say('Listen to the following menu options. '
               'For sales, press one. '
               'For support, press two. '
               'For our business hours, press three. '
               'To repeat these options, press nine. '
               'To speak with the receptionist, press zero.')
    return gather

"""
exit_menu() determine which state is called when the enter_state() function is called to transition to a new state.
Each number from the user input signifies a different route. 
"""
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

"""
3. Handle hours of operation
The hours state needs to play a recorded message with the business hours, and then give the caller the option to repeat the 
message when “1” is pressed, or return to the menu state when any other key is pressed.
"""

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

"""
4. State machine implementation 

Each state has a key in the IVR dictionary. The value associated with each state is a tuple with two elements: the “enter” and “exit” actions, respectively.

If the state is a terminal state that does not transition to any other state, then the exit action is None. 
Examples of this are the sales, support and reception states, which transfer the caller and do not ever return to the phone tree.

If the state needs to automatically transition to another state, without waiting for user input, then the exit action is a string 
with the name of the next state. The greeting and error tasks are in this category, as they automatically need to transition to the 
menu task after the enter action is executed.

If the state needs to accept user input to determine where to go next, then the exit action is a function that is invoked after 
input from the user is received.

"""

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

"""
5. Define the webhook
This webhook finds which state the caller is in from the Flask session variable and then it uses the enter_state() and exit_state() 
auxiliary functions to navigate the state machine. These two functions will find what the enter or exit actions are for the current 
state and return the appropriate TwiML code for Twilio to carry them out.
"""

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