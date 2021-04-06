from django.http import Http404, HttpResponse
from django.shortcuts import render
from django import template
from . import models
from elasticsearch import Elasticsearch

from rest_framework.decorators import api_view
from rest_framework.response import Response

import json
import os

ERR_QUERY_NOT_FOUND = '<h1>Query not found</h1>'
ERR_IMG_NOT_AVAILABLE = 'The requested result can not be shown now'

# USER = open("elastic-settings.txt").read().split("\n")[1]
# PASSWORD = open("elastic-settings.txt").read().split("\n")[2]
ELASTIC_INDEX = 'basic_indexing'

# open connection to Elastic
es = Elasticsearch(['http://localhost:9200/'], verify_certs=True)
register = template.Library()

if not es.ping():
    raise ValueError("Connection failed")

@register.filter
def subtract(value, arg):
    return value - arg

def Home(request):
    return render(request, 'seer/index.html')

def remove_punct(my_str):
    punctuations = '''!()-[]{};:'"\,<>./?@#$%^&*_~'''
    # To take input from the user
    # my_str = input("Enter a string: ")

    # remove punctuation from the string
    no_punct = ""
    for char in my_str:
        if char not in punctuations:
            no_punct = no_punct + char

    # display the unpunctuated string
    return no_punct

def remove_stop(query):
    CURRENT_DIRECTORY = os.path.realpath(os.path.dirname(__file__))
    ENGLISH_ST_PATH = os.path.join(CURRENT_DIRECTORY, 'englishST.txt')

    with open(ENGLISH_ST_PATH) as f:
        all_stopwords = f.readlines()
    # you may also want to remove whitespace characters like `\n` at the end of each line
    all_stopwords = [x.strip() for x in all_stopwords] 
    text_tokens = query.split(' ')
    query = [word for word in text_tokens if not word in all_stopwords]
    query = ' '.join(query)
    return query

@api_view(['GET'])
def search(request, query, page):
    
    nquery = query.lower()
    
    size = 15
    start = (page - 1) * size

#     body = {
#         "from": start,
#         "size": size,
#         "query": {  
#                     "multi_match": {
#                             "query": nquery,
#                             "fields":  ["question_body","answer_body", "question_head"],
#                             "type": "cross_fields"
#                         }
#         },
#         'highlight': {'fields': {'answer_body': {}, 'question_body': {}}}
#     }
#     body = {
#         "from": start,
#         "size": size,
#         "query": {
#     "bool": {
#       "filter": [
#          {"match_phrase": {"answer_body": { "query": nquery, "slop": 2}}},
#           {"match_phrase": {"question_body": { "query": nquery, "slop": 2}}},
#                     {"match_phrase": {"question_head": { "query": nquery, "slop": 2}}},

# #          {"match_phrase": {"question_head":  nquery}},
#           {  
#                     "multi_match": {
#                             "query": nquery,
#                             "fields":  ["question_body","answer_body", "question_head"],
# #                             "type": "cross_fields"
#                         }
#         }
#       ]
#     }
#  },'highlight': {'fields': {'answer_body': {}, 'question_body': {}}}
#     }
    
    body = {
        "from": start,
        "size": size,
  "query": {
    "query_string": {
      "query": nquery,
      "default_field": 'question_body'
    }
  }, 
        'highlight': {'fields': {'question_body': {}}}
}

    res = es.search(index=ELASTIC_INDEX, body=body)

    if not res.get('hits') or len(res) == 0 or res['hits']['total']['value'] == 0:
        raise Http404("Search query yields no results")
    else:

        totalresultsNumFound = res['hits']['total']['value']

        results = res['hits']['hits']

        SearchResults = []
        if len(results) > 0:
            for result in results:
                resultid = result['_id']
                f = {'resultid' : resultid}  # calling the object class that is defined inside models.py
                f['title'] = result['_source']['question_head']

                if len(f['title']) == 0:
                    continue

                f['content'] = result['_source']['question_body']


                f['url'] = result['_source']['url']

                print(result)
                f['description'] = ''
                if 'highlight' in result:
                    if 'question_body' in result['highlight']:
                        for desc in result['highlight']['question_body']:
                            f['description'] = f['description'] + desc + '\n'
                    if 'answer_body' in result['highlight']:
                        for desc in result['highlight']['answer_body']:
                            f['description'] = f['description'] + desc + '\n'
                f['description'] = f['description'][:400]
                SearchResults.append(f)
                
            context = dict()
            context['results'] = SearchResults

            context['total'] = totalresultsNumFound
            context['pageSize'] = size
            context['position'] = start + 1
            context['nextResults'] = len(results) + start
            context['prevResults'] = start - size

            context['page'] = (context['position'] // size) + 1
            context['nextPage'] = max(page + 1, 1)
            context['prevPage'] = page - 1

            numPages = (totalresultsNumFound // size) + 1

            if context['page'] <= 4:
                context['prevPageLimit'] = 1
            else:
                context['prevPageLimit'] = context['page'] - 4

            diff = numPages - context['page']

            if numPages - context['page'] < 4:
                context['nextPageLimit'] = context['page'] + diff
            elif context['prevPageLimit'] < 2:
                context['nextPageLimit'] = min(9, numPages)
            else:
                context['nextPageLimit'] = context['page'] + 4

            context['prevPageList'] = [i for i in range(context['prevPageLimit'], context['page'])]
            context['nextPageList'] = [i for i in range(context['page'] + 1, context['nextPageLimit'] + 1)]
            
#             print(context)
            return Response({"context": context})

        else:
#             print(context)
            raise Http404("Search query yields no results")



def Query(request):
    if request.method == 'GET':
        query = request.GET.get('query')
        page = int(request.GET.get('page', 1)) or 1

        if query is not None and len(query) > 1:
            # return __search(request, q, start, source, journal, full_text, abstract, author)
            return render(request, 'seer/results.html', {'query': query, 'page': page})
        else:
            return render(request, 'seer/index.html', {})


def Document(request, document_id):
    body = {
        "query": {
            "match": {
                "_id": document_id
            }
        }
    }
    res = es.search(index=ELASTIC_INDEX, body=body)
    results = res['hits']['hits']

    if len(results) == 0:
        raise Http404("Document does not exist")

    result = results[0]

    context = dict()
    context['docId'] = document_id
    context['title'] = result['_source']['metadata']['title']
    context['authors'] = __get_author_list(result)

    context['abstract'] = result['_source']['abstract']
    context['body'] = result['_source']['body_text']
    context['doi'] = result['_source']['doi']
    context['json'] = json.dumps(result, separators=(',', ':'))
    context['source'] = result['_source']['source_x']
    context['journal'] = result['_source']['journal']
    context['year'] = result['_source']['publish_year']
    context['similar_papers'] = ','.join(result['_source']['similar_papers'])

    if not context['journal']:
        context['journal'] = 'N/A'
    return render(request, 'seer/document.html', context)

