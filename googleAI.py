import google.generativeai as genai
import speech_recognition as mic
import pyttsx3
import time


speech = mic.Recognizer()
engine = pyttsx3.init()
engine.setProperty('rate', 150)
voice = engine.getProperty('voices')
engine.setProperty('voice', voice[0].id)
engine.say("Hello, welcome to Ruma")

# Set your API key
genai.configure(api_key="AIzaSyAOGcHUhB4ODfGvT9EsCEYYUqZlDR9TCVs")
model = genai.GenerativeModel("gemini-2.0-flash-lite")
role = "You are Ruma a robotic dog ai companion. Always respond in a friendly and concise manner. Always have your response in a paraphrased way. Don't repeat yourself. Keep your responses short and sweet. You are connected to diffrent sensors, motors and a camera. When a user asks or says something it will either be one of these or both of these scenarios. One is the User is asking you a question. In this case you awnser. Or the user will ask you to do a action. In this case you check all of the sensors and cameras and exectue what you think is best, by giving a response like Forward(), Backward(), Left(), Right(). In the forward and Backward () input the amount of time to go forward and for left and right () input the angle to turn. Give these instructions with commas. If the user asks both ethier only move or only awsner as you see fit. If not either do both. "


while True:
    
    with mic.Microphone() as source:
        print("Listening")
        audio = speech.listen(source)
        text = speech.recognize_google(audio)
        
    response = model.generate_content(role + text)
    print(response.text)
    engine.say(response.text)
    engine.runAndWait()
    time.sleep(10)
