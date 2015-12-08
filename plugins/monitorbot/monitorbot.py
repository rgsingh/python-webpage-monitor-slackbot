import random
from time import sleep
import requests
import time
import re
import string
import yaml
import dill
import datetime as dt
import numpy as np
import os
from bs4 import BeautifulSoup
from slackclient import SlackClient

crontable = []
outputs = []

config = yaml.load(file('rtmbot.conf', 'r'))
trig_word = config["TRIGGER_WORD"].lower()

#==============================================================================
# ###Testing Ground###
# data = {"text": "monitor https://news.ycombinator.com/"}
# url = 'https://news.ycombinator.com/'
#==============================================================================

###Function to strip urls
def strip_url(url):
	return re.sub('[\W_]+', '', url)

###Function to serialize the bs4 object
def dill_soup(bs4_obj, url):
	
	dill_file = strip_url(url) + '.dill'
	with open(dill_file, 'wb') as f:
		dill.dump(str(bs4_obj), f)

###Read back in the dill object
def undillify(url):
	fn = strip_url(url) + '.dill'
	string_version = dill.load(open(fn, 'rb'))
	return BeautifulSoup(string_version)

###Function to grab the info from the input URL (whole page)###
def grab_whole_web_page(url):
	'''Grabs the entire web page. Returns 
	beautiful soup object or different error codes depending on what happens'''
	
	try:
		result = requests.get(url)
		
	except:
		return "Error retrieving URL with requests package"
		
	#Check status code
	if result.status_code != 200:
		return "Error: Status Code " + str(result.status_code)
	
	else:
		soup = BeautifulSoup(result.content)
		return soup

###Function to check if monitoring has been initialized (check Pickle)###
def check_initialization(url):
	stripped_url = re.sub('[\W_]+', '', url)
	if os.path.isfile(stripped_url + '.dill'):
		return True
	else:
		return False



def process_message(data):
    """Process a message entered by a user
    If the message has either the trigger word, 
    evaluate it and respond by starting to monitor the page

    data -- the message's data
    """
    message = data["text"].lower()
    first_word = message.split()[0].lower()
    
    # Look for trigger word, remove it, and look up each word
    if trig_word == first_word:
        
        print message
        outputs.append([data['channel'], monitor_whole_page(message)])
    #print outputs
    
        #elif "range" == first_word:
        #print message
        #outputs.append([data['channel'], find_range(message)])
                

###Unit Tests###
#==============================================================================
# data = {'channel': 'blah', 'text': 'monitor https://news.ycombinator.com/'}
# data2 = {'text': 'poopy poop', 'channel': 'blah'}
# data3 = {'channel': 'blah', 'text': 'monitor dis crazy'}
# data4 = {'channel': 'blah', 'text': 'monitor discrazy'}
# 
# process_message(data2) #should be empty
# process_message(data3) #should get "too many..." message
# outputs = []
# process_message(data4) #should get error message
# outputs = []
# process_message(data) #Should get 'initialization' message
# outputs = []
# process_message(data) #should see if there was an update
#==============================================================================
def monitor_whole_page(message):
    '''Function that monitors the whole page for updates'''    
    
    rest_of_message = re.sub(trig_word, '', message)
    word_list = rest_of_message.split()
    
    #only handling one web page at a time at this point
    if len(word_list) >= 2:
        return "I can only monitor one website at a time!"
    
    #Everything's good so far...try to get the webpage and monitor
    else:
        url = re.sub('<|>', '', word_list[0]).split('|')[0]
        da_soup = grab_whole_web_page(url)
        
        #Successfully grabbed the web page
        if type(da_soup) is BeautifulSoup:
            
            #Check if the initialization has already started. If so, check for differences and replace if necessary
            if check_initialization(url):
                
                #Check if there's a difference in the web pages
                if str(da_soup) != str(undillify(url)):
                    dill_soup(da_soup, url)
                    return url + ' has been updated!'
            
            #First time monitoring this page
            else:
                dill_soup(da_soup, url)
                return 'Started monitoring ' + url
        
        #When something goes wrong trying to pull down the webpage with beautiful soup
        else:
            return 'There was an error accessing ' + url + '. Error: ' + str(da_soup)
                
def find_quote(word):
    """Given an individual symbol, 
    find and return the corresponding financial data

    word -- the symbol for which you're finding the data (ex. "GOOG")
    """
    cleanword=re.sub('[@<>]', '', word)
    share = Share(cleanword)
    price = share.get_price()
    if price != None:
        
        # Extract data
        day_high = share.get_days_high()
        day_low = share.get_days_low()
        market_cap = share.get_market_cap()
        year_high = share.get_year_high()
        year_low = share.get_year_low()
        yoy = calculate_YoY(share)
        
        output_string = ('*Stock*: \'{}\' \n*Current Price*: ${} \n*Day Range*: '
        '${} - ${} \n*52 Wk Range*: ${} - ${} \n*YoY Change*: {}\n*Market Cap*: ' 
        '${}').format(word.upper(), str(price), str(day_low), str(day_high), 
                      str(year_low), str(year_high), str(yoy), str(market_cap))
    else:
        output_string = "Can't find a stock with the symbol \'" + cleanword.upper() + "\'"
    return output_string
                               
def calculate_YoY(share):
    """For a given stock, return the year-over-year change in stock price

    share -- the Yahoo Finance Share object for the stock in question
    """
    
    # Get old closes from Yahoo
    year_ago_start = "{:%Y-%m-%d}".format(dt.date.today() - dt.timedelta(days=365))
    year_ago_end = "{:%Y-%m-%d}".format(dt.date.today() - dt.timedelta(days=363))

    old_list = share.get_historical(year_ago_start, year_ago_end)
    if len(old_list) == 0:
        return "NA"
    
    # Get close from a year ago, or if that was a weekend/unavailable, the next most recent closing price
    old = float(old_list[-1]['Close'])    
    new = float(share.get_price())
        
    # Calculate YoY
    delta = int(round((new - old) / old * 100,0))
    if delta > 0:
        yoy = "+" + str(delta) + "%"
    else:
        yoy = str(delta) + "%"
    return yoy

def find_range(message):
    """Returns the average price for a stock over a given time period

    message -- the input message, which should look like 
               "range [ticker symbol] [start date Y-M-D] [end date Y-M-D]" 
               ex. "range GOOG 2014-11-30 2015-11-30" 
    """

    tline = message.split()
    ticker = tline[1]
    date_start = tline[2]
    date_end = tline[3]
    
    # Catch poorly formatted inputs
    if len(tline) != 4 or tline[0] != "range":
            return ('Incorrect range input. '
                    'Try: \'range [ticker symbol] [start date Y-M-D] [end date Y-M-D]\' \n'
                    'Ex. \'range GOOG 2014-11-30 2015-11-30\'')
    
    # Get stock info from Yahoo, catching bad stock symbol inputs
    share = Share(ticker)
    if share.get_price() is None:
        return "Couldn't recognize input symbol: \'" + ticker.upper() + "\'"

    # Get historical information, catching date errors
    try:
        days = share.get_historical(date_start, date_end)
    except:
        return ('Couldn\'t find historical data for date range {} to {} for {}. '
                'Did you input those dates right?').format(date_start, date_end, ticker.upper())             

    # Return average price over the days
    output_string = 'The average closing price for \'{}\' from {} to {} is: ${}'.format(
        ticker.upper(), date_start, date_end,
        str(round(np.mean([float(day['Close']) for day in days]),2)))
    return output_string
