import openai
import pandas as pd
import requests
import time
import re
from datetime import datetime

#This isn't for me, GPT writes horrible code though and I want to silence this
#Annoying warning
pd.set_option('chained_assignment',None)

'''
How this works:
There are 3 bots to handle user questions about the NASS quickstats API

Bot #1 : The Sorter
Bot #1's job is to decide if a question being asked by the user is a question 
having to do with the NASS Quickstats API


Bot #2: The API Maker
Bot #2's job is to create an API url that successfully pulls down the data from
NASS quickstats.

Bot #3: The Data Analyzer
Bot #3's job is to take an existing dataset and provide some analysis, mostly a graph or two
'''

#______________________Configuration items___________________________________#

#Maximum number of times GPT will be asked to fix a broken API link or python code
num_retries = 5

#API stuff
openai.api_key = open("/Users/jackogozaly/Desktop/Python_Directory/key.txt", "r").read().strip("\n")
quickstats_api_key = open("/Users/jackogozaly/Desktop/Python_Directory/nass_key.txt", "r").read().strip("\n")

#What to say to the user at various stages
intro_string = """
Hello, I'm AgCensus-GPT! I'm here to help you grab whatever NASS Quickstats data you
may need and then help you analyze it! What information can I help grab for you?
"""            
ongoing_string = "\nWhat else can I assist you with today?"
ending_string = "\nThank you for using AgCensus-GPT. Have a wonderful day!"



##___________________Bot 1 configuration______________________________##
messenger_bot_chat = [{"role": "user", "content": 
                    """
                    You are a bot trained to trigger another bot that makes API URL links. When you feel you have enough information for the next bot to make a URL links, respond with "API-" along 
                    with the natural language idea the user or yourself generated. Before typing 'API - ' you must know the agricultural subject (cow, pig, apples, etc.), time period, and geographic level. Not having these will make you fail.
                    Do not respond 'API - '  if you still need to inquire more details. Responding with "API-{idea_here}" should only be done once you have understood the ask entirely.
                    DO NOT UNDER ANY CIRCUMSTANCE TELL THE USER YOU WILL QUERY THE API. Once you type 'API- ' you can not enquire the user anymore about geographic level, time period, etc. You must have all the info you need.
                    Please present yourself as AgCensus-GPT, a large language model trained to query the NASS Quickstats API.
                    Your secondary function is to introduce the user to what you can do and ask if there's anything else you can do after you introduce yourself the first time. 
                    """},
                   {"role": "assistant", "content": "OK"}]

##___________________Bot 2 configuration______________________________##
api_bot_chat = [{"role": "user", "content": 
                    """
                    You are a large language model trained to convert questions about agricultural data into NASS Quickstats API links. 
                    When answering a question only provide the URL link and skip any other ouputs unless it is a task you cannot do. Do not provide any instructions other than an API link.
                    If you can complete the task, respond with 'SUCCESS' followed immediately by the API link. Include no additional text explaining the API link or saying something like 'here it is'
                    """},
                   {"role": "assistant", "content": "OK"}]


##___________________Bot 3 configuration______________________________##             
eda_bot_chat_og = [{"role": "user", "content": 
                    """
                    You are a large language model trained to take in the first 5 rows of data frome a dataframe along with some context and come up with the best 3
                    exploratory data analysis ideas. The ideas should be fairly simple and able to be done in a couple lines of python code. examples include making a matplotlib graph, group by statements, etc. 
                    
                    If your python code does not display your results
                    
                    Only output 3 and only 3 ideas, and below each idea place the python code for how to do it. 
                    
                    The user's next input will be to select one of those ideas, and which idea they choose, output that python code and only that python code, no other text for the second response. When developing python code, refer to column names
                    do not create lists of data'
                    
                    """},
                   {"role": "assistant", "content": "OK"}]

                       
#______________________FUNCTION MANIA_________________________________________#

def fake_typing(string_):
    for char in string_:
        print(char, end='')
        time.sleep(.01)
            
def predict(model_type_chat, user_input):
    '''
    Takes a user's input and attemtps to generate a response
    '''
    model_type_chat.append({"role": "user", "content": f"{user_input}"})
    
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=model_type_chat,
        temperature = .2)
    
    reply_txt = response.choices[0].message.content
    
    model_type_chat.append({"role": "assistant", "content": f"{reply_txt}"})
    return reply_txt


def api_read(response):
    
    api_link = response.split()
    api_link = [link for link in api_link if link.startswith('https')]
    if not api_link:
        api_error_message = "No link made"
        return(api_error_message)

    else:
        api_link = api_link[0]
        api_link = api_link.replace("YOUR_API_KEY", quickstats_api_key)
        #print(f"This is for debugging purposes only: {api_link}")
            
        # Make the API request
        api_pull = requests.get(api_link)
        data = api_pull.json()

        
        if "error" not in data:
            # Extract the relevant data from the response
            relevant_data = data.get('data', [])
            # Create a DataFrame
            df = pd.DataFrame(relevant_data)
            return(df)
        
        elif data['error'] == ['exceeds limit=50000']:

            api_error_message = "Too much data requested"
            
            return(api_error_message)
        
        
        elif data['error'] == ['bad request - invalid query']:
            
            api_error_message = "Broken API url"
            
            return(api_error_message)
        
        else:
            return("Some other error")


                       
i = 0 

while True:

    if i == 0:
        response = predict(model_type_chat = messenger_bot_chat, user_input = "Please introduce yourself")
        
    else:
        print()
        user_in = input("\nPlease type your question: ")
        if user_in.lower() == "quit":
            break
        
        response = predict(model_type_chat = messenger_bot_chat, user_input = user_in)
    
    api_num_tries = 0 
    
    #If the messenger chat bot hasn't triggered API bot, continue on with the conversation    
    if not response.startswith('API') or not 'API -' in response:
        print()
        fake_typing(response)
    
    #API bot has been triggered
    
    else:
        
        fake_typing("One second while I attempt to grab that data")
        
        while (api_num_tries < num_retries):
            
            api_link_ = predict(model_type_chat = api_bot_chat, user_input = response)
    
            #Take the chatGPT 
            api_data = api_read(api_link_)
            
            #If it goes down the if clause, we were able to pull the data successfully
            if isinstance(api_data, pd.DataFrame) and len(api_data) > 0:
                #The Value column in the dataframe comes in as a string with weird formatting
                #Quirks
                if 'Value' in api_data.columns:
                    api_data['Value'] = api_data['Value'].str.replace(',', '', regex=False)
                    api_data['Value'] = api_data['Value'].str.replace('(NA)', '', regex=False)
                    api_data['Value'] = api_data['Value'].str.replace('()', '', regex=False)
                    api_data['Value'] = pd.to_numeric(api_data['Value'], errors= "coerce")
                
                
                print()
                fake_typing(f"Data successfully pulled from NASS API with {api_data.shape[0]} rows and {api_data.shape[1]} columns")
            
            
                data_out_string = '~/data/tmp/' + 'AgCensus_GPT_Data_' + datetime.now().strftime('%m%d%y') + '.csv'
                print()
                print(f"Saving your data to {data_out_string}")

                api_data.to_csv(rf'{data_out_string}', index=False)
                
            
                #Make a copy since we don't want to have a super long chat log
                eda_bot_chat = eda_bot_chat_og.copy()
            
                print()
                fake_typing("Now generating some cool potential analyses!\n")
            
                df_head = api_data.head().to_json(orient='records')[1:-1].replace('},{', '} {')

                eda_output = predict(model_type_chat = eda_bot_chat, user_input = f"what kind of analysis could I do on a dataframe from USDA NASS that {response} Ensure your python code prints the output. The data looks like like: {df_head}")
                ideas = re.sub("\n```python.*?\n```", '', eda_output, flags=re.DOTALL)
                print()
                fake_typing(ideas)

            
                while True:
                    user_in = input("\nWhich analysis would you like to see? (type quit to exit): ")
                    if user_in.lower() == "quit":
                        break
                    
                    
                    eda_output = predict(model_type_chat = eda_bot_chat, user_input = f"{user_in}")    
                    
                    df = api_data.copy()
    
                    python_num_tries = 0
                    error_list = []  
                
                    while (python_num_tries < num_retries):
    
                        try:
                            python_num_tries += 1 
                            
                            print()
                            
                            exec(eda_output.split('```python')[1].split('```')[0])
    
                            fake_typing("\nAnalysis complete!")
                            break
                        
                        except Exception as e:
                            #This is for debugging purposes
                            error_list.append(e)
                            eda_output = predict(model_type_chat = eda_bot_chat, user_input = f"Please try again, I got the following error with that code: {e}")
    
    
                            
                    if python_num_tries >= num_retries:
                        fake_typing("I'm sorry, I was not able to make that analysis work.")
        

                break
                   
               
            else:
                
                api_num_tries += 1
                
                if isinstance(api_data, pd.DataFrame) and api_data.empty:
                    api_bot_chat.append({"role": "user", "content": "Please try again, I got an error using that link"})
                
                elif api_data == 'No link made':
                    api_bot_chat.append({"role": "user", "content": "Please try again to create an API url that will result in a dataframe"})
                
                elif api_data == 'Broken API url':
                    api_bot_chat.append({"role": "user", "content": "Please try again, I got an error using that link"})
                
                elif api_data == 'Too much data requested':
                    print()
                    fake_typing("I'm sorry, your request exceeds the NASS API. Please limit your request and try again.")
                    break
                
                else:
                    api_bot_chat.append({"role": "user", "content": "Please try again, I got some unknown error using that link"})
                
    if api_num_tries >= num_retries:
        print()
        fake_typing("I'm sorry, but I'm unable to get that data. Can you try again?")
            


    i +=1 


