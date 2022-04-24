from pymongo import *
"""
CRUD OPERATIONS with MongoDB
"""

# Create the client
client = MongoClient('localhost', 3001)

# Connect to our database
db = client['MurTeamBot_alpha']

# Fetch our series collection
teams_values = db['users']
# вспомогательная коллекция, где хранятся данные, какие картинки просмотрены, а какие - нет
admin_sessions = db['sessions']
# база данных с сессиями админов (например, разметки изображений)
teams = db['teams']
# основная БД с командами


def insert_document(collection, data):
    """ Function to insert a document into a collection and
    return the document's id.
    """
    return collection.insert_one(data).inserted_id


def find_document(collection, elements, multiple=False):
    """ Function to retrieve single or multiple documents from a provided
    Collection using a dictionary containing a document's elements.
    """
    if multiple:
        results = collection.find(elements)
        return [r for r in results]
    else:
        return collection.find_one(elements)


def update_document(collection, query_elements, new_values, unset_keys={}):
    """ Function to update a single document in a collection.
    """
    collection.update_one(
        query_elements, {'$set': new_values, '$unset': unset_keys})


def delete_document(collection, query):
    """ Function to delete a single document from a collection.
    """
    collection.delete_one(query)
