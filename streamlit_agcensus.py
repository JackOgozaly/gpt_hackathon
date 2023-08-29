import streamlit as st
import openai
import pandas as pd
import requests
import time
import re
from datetime import datetime


# To run this script use streamlit run
#on the command line


#______________________Configuration items___________________________________#

#Maximum number of times GPT will be asked to fix a broken API link or python code
num_retries = 5

#API stuff
openai.api_key = open("/Users/jackogozaly/Desktop/Python_Directory/key.txt", "r").read().strip("\n")
quickstats_api_key = open("/Users/jackogozaly/Desktop/Python_Directory/nass_key.txt", "r").read().strip("\n")



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
                    
                    If your python code does not display your results you will fail. You are in a stremlit environment. All final results need to be outputted for streamlit. So if it's a plot, you would need to save a figure and do:
                        st.pyplot(fig), if it's a dataframe it would be st.dataframe(df)
                    
                    For all figures, set their size to figsize=(width, height). DO NOT ENTER VAUES INTO IT
                    
                    If you do not do this nothing will print and you will have failed.
                    
                    Only output 3 and only 3 ideas, and below each idea place the python code for how to do it. 
                    
                    The user's next input will be to select one of those ideas, and which idea they choose, output that python code and only that python code, no other text for the second response. When developing python code, refer to column names
                    do not create lists of data'
                    
                    """},
                   {"role": "assistant", "content": "OK"}]

                    
                    
#______________________FUNCTION MANIA_________________________________________#       
                    
def api_read(response):
    '''
    Takes the output of API bot and grabs the data
    '''
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
        
        try:
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
            
        except:
            api_error_message = "Broken API url"
            
            return(api_error_message)
                    
                    
def predict(model_type_chat, user_input, model):
    '''
    Takes a user's input and attemtps to generate a response
    '''
    model_type_chat.append({"role": "user", "content": f"{user_input}"})
    
    response = openai.ChatCompletion.create(
        model=model,
        messages=model_type_chat,
        temperature = .2)
    
    reply_txt = response.choices[0].message.content
    
    model_type_chat.append({"role": "assistant", "content": f"{reply_txt}"})
    return reply_txt
               

def fake_typing(text):
    '''
    This function should be placed within a 
    with st.chat_message("assistant"):
    '''
    
    #These are purely cosmetic for making that chatbot look
    message_placeholder = st.empty()
    full_response = ""
    
    # Simulate stream of response with milliseconds delay
    for chunk in text.split():
        full_response += chunk + " "
        time.sleep(0.05)
        # Add a blinking cursor to simulate typing
        message_placeholder.markdown(full_response + "▌")

    # Add assistant response to chat history
    st.session_state.messages.append({"role": "assistant", "content": full_response})
    


st.set_page_config(layout="wide")
#Website Name
st.title("AgCensusGPT")
# Sidebar - let user choose model
st.sidebar.title("Chatbot Options")
model_name = st.sidebar.radio("Choose a model:", ("GPT-3.5", "GPT-4"))

width = st.sidebar.slider("plot width", 1, 25, 3)
height = st.sidebar.slider("plot height", 1, 25, 1)

# Map model names to OpenAI model IDs
if model_name == "GPT-3.5":
    model = "gpt-3.5-turbo"
else:
    model = "gpt-4"
                       
                       
                       

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Initialize chat history
if "analysis" not in st.session_state:
    st.session_state.analysis = False


#Initialize Counter
if 'count' not in st.session_state:
    st.session_state.count = 0

if 'analysis_count' not in st.session_state:
    st.session_state.analysis_count = 0
    
if 'saved_api_data' not in st.session_state:
    st.session_state.saved_api_data = None
    
if 'eda_convo' not in st.session_state:
    st.session_state.eda_convo = None

    
# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])



#Only introduce the chatbot to the user if it's their first time logging in
if st.session_state.count == 0:
    response = predict(model_type_chat = messenger_bot_chat, user_input = "Please introduce yourself",
                       model = model)    
    #Output introduction message
    fake_typing(response)
    
#Update our counter so we don't repeat the introduction
st.session_state.count += 1

# Accept user input
if prompt := st.chat_input("What is your question?"):
    
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    # Display user message in chat message container
    with st.chat_message("user"):
        st.markdown(prompt)

    # Display assistant response in chat message container
    with st.chat_message("assistant"):

        #Chat GPT response
        response = predict(model_type_chat = messenger_bot_chat, user_input = prompt,
                           model= model)    
        
        api_num_tries = 0 
        #If the messenger chat bot hasn't triggered API bot, continue on with the conversation    
        if (not response.startswith('API') or not 'API -' in response) and st.session_state.analysis is False:
            #Cosmetic to make it appear like it's typing
            fake_typing(response)
        
        elif (response.startswith('API') or not 'API -' in response) and st.session_state.analysis is False:
            fake_typing("One second while I attempt to grab that data")
            master_break = False            
            
            while (api_num_tries < num_retries):
                
                
                if master_break is True:
                    break
                
                api_link_ = predict(model_type_chat = api_bot_chat, user_input = response, model = model)
        
                #Take the chatGPT 
                api_data = api_read(api_link_)
                
                #If it goes down the if clause, we were able to pull the data successfully
                if isinstance(api_data, pd.DataFrame) and len(api_data) > 0 and api_data.shape[0] > 1:
                    #The Value column in the dataframe comes in as a string with weird formatting
                    #Quirks
                    if 'Value' in api_data.columns:
                        api_data['Value'] = api_data['Value'].str.replace(',', '', regex=False)
                        api_data['Value'] = api_data['Value'].str.replace('(NA)', '', regex=False)
                        api_data['Value'] = api_data['Value'].str.replace('()', '', regex=False)
                        api_data['Value'] = pd.to_numeric(api_data['Value'], errors= "coerce")
    
                    fake_typing(f"Data successfully pulled from NASS API with {api_data.shape[0]} rows and {api_data.shape[1]} columns")
                    
                    
                    
                    #Since we successfully pulled the data, trigger EDA bot
                    st.session_state.analysis = True
                    #Make a copy since we don't want to have a super long chat log
                    eda_bot_chat = eda_bot_chat_og.copy()
                
                    fake_typing("Now generating some cool potential analyses!\n")
            
                    df_head = api_data.head().to_json(orient='records')[1:-1].replace('},{', '} {')

                    eda_output = predict(model_type_chat = eda_bot_chat, user_input = f"what kind of analysis could I do on a dataframe from USDA NASS that {response} Ensure your python code prints the output. The data looks like like: {df_head}",
                                     model= model)
                    
                    ideas = re.sub("\n```python.*?\n```", '', eda_output, flags=re.DOTALL)

                    fake_typing(ideas)
                
                    
                    st.session_state.saved_api_data = api_data
                    
                    
                    
                    st.session_state.eda_convo = eda_bot_chat
                    
                    master_break = True
                
                
                else:
                    
                    api_num_tries += 1
                    
                    if isinstance(api_data, pd.DataFrame) and api_data.empty:
                        api_bot_chat.append({"role": "user", "content": "Please try again, I got an error using that link"})
                    
                    elif api_data == 'No link made':
                        api_bot_chat.append({"role": "user", "content": "Please try again to create an API url that will result in a dataframe"})
                    
                    elif api_data == 'Broken API url':
                        api_bot_chat.append({"role": "user", "content": "Please try again, I got an error using that link"})
                    
                    elif api_data == 'Too much data requested':

                        fake_typing("I'm sorry, your request exceeds the NASS API. Please limit your request and try again.")
                        master_break = True
                        break
                    
                    else:
                        api_bot_chat.append({"role": "user", "content": "Please try again, I got some unknown error using that link"})
                        
            
        else:
                
            if prompt.lower() == "quit":
                master_break = True
                st.session_state.analysis = False

                
            else:
            
                eda_bot_chat = st.session_state.eda_convo.copy()
            
                eda_output = predict(model_type_chat = eda_bot_chat, user_input = f" REMEMBER YOU ARE IN A STREAMLIT ENVIRONMENT. PLEASE ENSURE YOUR PROPERLY PRINT RESULTS FOR the following and set clear_figure=False: {prompt}", model = model)    
                
                df = st.session_state.saved_api_data.copy()
    
                python_num_tries = 0
                error_list = []  
            
                while (python_num_tries < num_retries):
    
                    try:
                        python_num_tries += 1 
                        
                        exec(eda_output.split('```python')[1].split('```')[0])
    
                    
                        fake_typing("\nAnalysis complete!")
                        
                        st.session_state.eda_convo = eda_bot_chat
                        
                        break
                    
                    except Exception as e:
                        #This is for debugging purposes
                        error_list.append(e)
                        eda_output = predict(model_type_chat = eda_bot_chat, user_input = f"Please try again, I got the following error with that code: {e}",
                                             model= model)
                        
                        st.session_state.eda_convo = eda_bot_chat
                        
                if python_num_tries >= num_retries:
                    fake_typing("I'm sorry, I was not able to make that analysis work.")
                
            
                st.session_state.analysis_count += 1

                
                
                
        
            
                    
        if api_num_tries >= num_retries:
            fake_typing("I'm sorry, but I'm unable to get that data. Can you try again?")
            
        
        
        

        
                    
                    
                    
                    
    
    
    


