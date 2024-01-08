from unittest import result
from flask import Flask,redirect, url_for, request
import os
import sys
import json
import math
import string
import re
import logging
import getopt
import configparser
from importlib import import_module
import urllib.parse

curr_dir = os.path.dirname(os.path.realpath(__file__))
os.chdir(curr_dir)
os.getcwd()

sys.path.insert(1, os.path.abspath(os.path.join(curr_dir, os.pardir)))
sys.path.append("../base-classes")
sys.path.append("../llm-service")
sys.path.append("../vectordb")
sys.path.append("../common-functions")
sys.path.append("../common-objects")
from aiwhisprBaseClasses import baseLlmService, vectorDb 
import aiwhisprConstants


aiwhispr_home =os.environ['AIWHISPR_HOME']
aiwhispr_logging_level = os.environ['AIWHISPR_LOG_LEVEL']
print("AIWHISPR_HOME=%s", aiwhispr_home)
print("LOGGING_LEVEL", aiwhispr_logging_level)

import logging

if (aiwhispr_logging_level == "Debug" or aiwhispr_logging_level == "DEBUG"):
   logging.basicConfig(level = logging.DEBUG,format = '[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s')
elif (aiwhispr_logging_level == "Info" or aiwhispr_logging_level == "INFO"):
   logging.basicConfig(level = logging.INFO,format = '[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s')
elif (aiwhispr_logging_level == "Warning" or aiwhispr_logging_level == "WARNING"):
   logging.basicConfig(level = logging.WARNING,format = '[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s')
elif (aiwhispr_logging_level == "Error" or aiwhispr_logging_level == "ERROR"):
   logging.basicConfig(level = logging.ERROR,format = '[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s')
else:   #DEFAULT logging level is DEBUG
   logging.basicConfig(level = logging.DEBUG,format = '[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s')

class searchHandler:
   model:baseLlmService
   vector_db:vectorDb
   limit_hits=25
   content_site_name:str
   src_path:str
   src_path_for_results:str
   logger=logging.getLogger(__name__)

   def setup(self,llm_service_module:str, vectordb_module:str, llm_service_config:dict, vectordb_config:dict, content_site_name:str,src_path:str,src_path_for_results:str):
      llmServiceMgr = import_module(llm_service_module)
      vectorDbMgr = import_module(vectordb_module)

      self.vector_db = vectorDbMgr.createVectorDb(vectordb_config=vectordb_config,
                                          content_site_name = content_site_name,
                                          src_path = src_path,
                                          src_path_for_results = src_path_for_results)

      self.vector_db.connect()
      self.content_site_name = content_site_name
      self.src_path = src_path
      self.src_path_for_results = src_path_for_results

      self.model= llmServiceMgr.createLlmService(llm_service_config)
      self.model.connect()

   def search(self,input_query:str, result_format:str, textsearch_flag:str, content_path=""): 

      output_format = result_format      
      self.logger.debug("result format: %s", result_format)
      if output_format not in ['html','json']:
         self.logger.error("cannot handle this result format type")
      if textsearch_flag not in ['Y', 'N']:
         self.logger.error("text search flag should be a Y or N")
      
      self.logger.debug("get vector embedding for text:{%s}",input_query)
      query_embedding_vector =  self.model.encode(input_query)
      query_embedding_vector_as_list = query_embedding_vector
      vector_as_string = ' '. join(str(e) for e in query_embedding_vector_as_list)
      self.logger.debug("vector embedding:{%s}",vector_as_string)

      if textsearch_flag == 'Y':
         pass_input_query = input_query
         self.logger.debug("Search will include text search results")
      else:
         pass_input_query = ""

      if len(content_path) > 0:
         search_results = self.vector_db.search(self.content_site_name,query_embedding_vector_as_list, self.limit_hits ,pass_input_query, content_path)
      else:
         search_results = self.vector_db.search(self.content_site_name,query_embedding_vector_as_list, self.limit_hits ,pass_input_query)
      
      display_html = '<div class="aiwhisprSemanticSearchResults">'
      display_json = []

      

      """""
        We should receive a JSON Object in the format 
        {"results": [ semantic_results{} ,text_results{}  ]}
       
         semantic_results / text_results will be a format 
         {
         "found" : int
         "type"  : semantic / text / image 
         "hits"  : []
         }
             
             hits[]  will be a list Example : hits[ {"result":{},   {"result":{} }]
            "result": {
               id: UUID,
               content_site_name: str,
               content_path:str,
               src_path:str,
               src_path_for_results,
               tags:str,
               text_chunk:str,
               text_chunk_no:int,
               title:int,
               last_edit_date:float,
               vector_embedding_date:float,
               match_score: float,
            }
      """""
      
      self.logger.debug('SearchService received search results from vectordb:')
      self.logger.debug(json.dumps(search_results))

      no_of_semantic_hits = search_results['results'][0]['found']
     

      i = 0
      while i < no_of_semantic_hits:
         chunk_map_record = search_results['results'][0]['hits'][i]
         content_site_name = chunk_map_record['content_site_name']
         record_id = chunk_map_record['id']
         content_path = chunk_map_record['content_path']
         src_path = chunk_map_record['src_path']
         #src_path_for_results = chunk_map_record['src_path_for_results']
         src_path_for_results = self.src_path_for_results
         text_chunk = chunk_map_record['text_chunk']
         title = chunk_map_record['title']
         tags = chunk_map_record['tags']

         if output_format == 'html':
            
            if src_path_for_results[0:4] == 'http': 
               display_url = urllib.parse.quote_plus(src_path_for_results,safe='/:')  + '/' + urllib.parse.quote(content_path)
            else:
               display_url = src_path_for_results + '/' + content_path


            if len(text_chunk) <= aiwhisprConstants.HTMLSRCHDSPLYCHARS:
               display_text_chunk = text_chunk
            else:
               display_text_chunk = text_chunk[:(aiwhisprConstants.HTMLSRCHDSPLYCHARS -3)] + '...'
            
            if len(title) > 0: #Display title with link to content
                display_html = display_html + '<a href="' + display_url + '">' + title + '</a><br>'
            else:  #display the content path
               display_html = display_html + '<a href="' + display_url + '">' + content_path + '</a><br>'
            
            display_html = display_html + '<div><p>' + display_text_chunk + '</p></div><br>'
            
         if output_format == 'json':
            json_record = {} #Dict
            json_record['content_path'] = content_path
            json_record['id'] = record_id
            json_record['content_site_name'] = content_site_name
            json_record['src_path'] = src_path
            json_record['src_path_for_results'] = src_path_for_results
            json_record['text_chunk'] = text_chunk
            json_record['search_type'] = 'semantic'
            json_record['title'] = title
            json_record['tags'] = tags
            ##Add this dict record in the list
            display_json.append(json_record)
      
         i = i + 1 
      
      display_html = display_html + '</div>'

      if textsearch_flag == "Y": ## Process second batch of results which are from the text search
         display_html = display_html + '<div class="aiwhisprTextSearchResults">'
         
         j = 0
         if len(search_results['results']) > 1: #Check that  text results are there.
                no_of_text_hits = len(search_results['results'][1]['hits'])
         else:
            self.logger.info('No Text Results returned')

         while j < no_of_text_hits:
            chunk_map_record = search_results['results'][1]['hits'][j]
            content_site_name = chunk_map_record['content_site_name']
            record_id = chunk_map_record['id']
            content_path = chunk_map_record['content_path']
            src_path = chunk_map_record['src_path']
            #src_path_for_results = chunk_map_record['src_path_for_results']
            src_path_for_results = self.src_path_for_results
            text_chunk = chunk_map_record['text_chunk']
            title = chunk_map_record['title']
            tags = chunk_map_record['tags']
               
            if output_format == 'html':

               if src_path_for_results[0:4] == 'http':
                  display_url = urllib.parse.quote_plus(src_path_for_results,safe='/:')  + '/' + urllib.parse.quote(content_path)
               else:
                  display_url = src_path_for_results + '/' + content_path

               if len(text_chunk) <= aiwhisprConstants.HTMLSRCHDSPLYCHARS:
                  display_text_chunk = text_chunk
               else:
                  display_text_chunk = text_chunk[:(aiwhisprConstants.HTMLSRCHDSPLYCHARS -3)] + '...'

               if len(title) > 0: #Display title with link to content
                  display_html = display_html + '<a href="' + display_url + '">' + title + '</a><br>'
               else:  #display the content path
                  display_html = display_html + '<a href="' + display_url + '">' + content_path + '</a><br>'

               display_html = display_html + '<div><p>' + display_text_chunk + '</p></div><br>'
               
            if output_format == 'json':
               json_record = {} #Dict
               json_record['content_path'] = content_path
               json_record['id'] = record_id
               json_record['content_site_name'] = content_site_name
               json_record['src_path'] = src_path
               json_record['src_path_for_results'] = src_path_for_results
               json_record['text_chunk'] = text_chunk
               json_record['search_type'] = 'text'
               json_record['title'] = title
               json_record['tags'] = tags
               ##Add this dict record in the list
               display_json.append(json_record)
         
            j = j + 1 
         
         display_html = display_html + '</div>'

      #Return based on result_format
      if output_format == 'json':
         return { 'results': display_json} #Return as dict
      else:
         return display_html
           
         

mySearchHandler = []

def setup(configfile):
    
    #interpolation is set to None to allow reading special symbols like %
    config =  configparser.ConfigParser(interpolation=None)
    config.read(configfile)

    #Read the content site configs
    content_site_name = config.get('content-site','sitename')
    src_path = config.get('content-site','srcpath')
    src_path_for_results = config.get('content-site','displaypath')
    ##VectorDB Service
    vectordb_config = dict(config.items('vectordb'))
    vectordb_module = config.get('vectordb','vectorDbModule')
    ##LLM Service
    llm_service_config = dict(config.items('llm-service'))
    llm_service_module = config.get('llm-service', 'llmServiceModule')
    mySearchHandler[0].setup(llm_service_module, vectordb_module, llm_service_config, vectordb_config, content_site_name,src_path,src_path_for_results)

app = Flask(__name__)

@app.route('/')
def say_hello():
   return '<center>Welcome. Your local AIWhispr  service is up</center>'

#This is the search function that does a semantic vector search
@app.route('/aiwhispr',methods = ['POST', 'GET'])
def semantic_search():

   if request.method == 'POST':
      input_query = request.form['query']
      result_format = request.form['resultformat']
      textsearch_flag = request.form['withtextsearch']
      content_path = request.form['contentpath']
   else:
      input_query = request.args.get('query')
      result_format = request.args.get('resultformat')
      textsearch_flag = request.args.get('withtextsearch')
      content_path = request.args.get('contentpath')

   if result_format == None or len(result_format) == 0:
      result_format = 'json' #Default
   if textsearch_flag == None or len(textsearch_flag) == 0 or textsearch_flag == 'N' or textsearch_flag == "no" or textsearch_flag == "No":
      textsearch_flag = 'N'
   if textsearch_flag == 'Y' or textsearch_flag == "yes" or textsearch_flag == "Yes":
      textsearch_flag = 'Y'
   
   if content_path == None or len(content_path) == 0:
      content_path = '' #empty string
   

   return mySearchHandler[0].search(input_query, result_format, textsearch_flag,content_path)


### END OF FUNCTION SEARCH

if __name__ == '__main__':
   #The list based approach enabled pass be reference
   mySearchHandler.append(searchHandler())
   
   configfile=''
   serviceportnumber=0

   opts, args = getopt.getopt(sys.argv[1:],"hC:H:P:",["configfile=","servicehostip==","serviceportnumber="])
   for opt, arg in opts:
      if opt == '-h':
         print('This uses flask so provide full path to python3 for the python script and the config file in command line argument')
         print('<full_directory_path>/searchService.py -C <config file of the content site> -P<flask port number on which this service should listen> ' )
         sys.exit()
      elif opt in ("-C", "--configfile"):
         configfile = arg
      elif opt in ("-H", "--servicehostip"):
         servicehostip = arg
      elif opt in ("-P", "--serviceportnumber"):
         serviceportnumber = int(arg)

   setup(configfile)
   app.run(debug=True,host=servicehostip, port=serviceportnumber)

