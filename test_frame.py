import sys

def create_event():
    frame = sys._getframe(1)
    print("Caller is:", frame.f_code.co_name)

send = create_event

def my_client_function_calling_create_event():
    create_event()

def my_client_function_calling_send():
    send()

my_client_function_calling_create_event()
my_client_function_calling_send()
