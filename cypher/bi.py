from neo4j import GraphDatabase, time
from datetime import datetime
from neo4j.time import DateTime, Date
import time
import pytz
import csv
import re

result_mapping = {
     1: ["int32", "bool", "int32", "int32", "float32", "int32", "float32"],
     2: ["string", "int32", "int32", "int32"],
     3: ["id", "string", "datetime", "id", "int32"],
     4: ["id", "string", "string", "datetime", "int32"],
     5: ["id", "int32", "int32", "int32", "int32"],
     6: ["id", "int32"],
     7: ["string", "int32"],
     8: ["id", "int32", "int32"],
     9: ["id", "string", "string", "int32", "int32"],
    10: ["id", "string", "int32"],
    11: ["int64"],
    12: ["int32", "int32"],
    13: ["id", "int32", "int32", "float32"],
    14: ["id", "id", "string", "int32"],
    15: ["[id]", "float32"],
    16: ["id", "int32", "int32"],
    17: ["id", "int32"],
    18: ["id", "int32"],
    19: ["id", "id", "float32"],
    20: ["id", "int64"],
}

def convert_value(value, type):
    if type == "[id]" or type == "[int64]":
        return int(value) # todo parse list
    elif type == "bool":
        return bool(value)
    elif type == "datetime":
        print("datetime") # what is the return value of Neo4j in this case?
    elif type == "float32":
        return float(value)
    elif type == "id" or type == "int64":
        return int(value)
    elif type == "int32":
        return int(value)
    elif type == "string":
        return str(value)
    else:
        raise ValueError("type not found")

#@unit_of_work(timeout=300)
def query_fun(tx, query_num, query_spec, query_parameters):
    results = tx.run(query_spec, query_parameters)
    mapping = result_mapping[query_num]
    k = 0
    for result in results:
        for i, type in enumerate(mapping):
            value = result[i]
            converted = convert_value(value, type)
            print(f"attribute [{i}] type: {type}, value: {value}, converted value: {converted}")
            # todo: use list comprehension
            # convert to date/time
        print()
        k = k + 1
    print(f'{k} results')


def run_query(session, query_num, query_id, query_spec, query_parameters):
    print(f'Q{query_id}: {query_parameters}')
    start = time.time()
    results = session.read_transaction(query_fun, query_num, query_spec, query_parameters)
    end = time.time()
    duration = end - start
    #print("Q{}: {:.4f} seconds, {} tuples".format(query_id, duration, results[0]))

def convert_to_datetime(timestamp):
    dt = datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%S.%f+00:00')
    return DateTime(dt.year, dt.month, dt.day, 0, 0, 0) # also passing pytz.timezone('GMT') causes an exception

def convert_to_date(timestamp):
    dt = datetime.strptime(timestamp, '%Y-%m-%d')
    return Date(dt.year, dt.month, dt.day)

driver = GraphDatabase.driver("bolt://localhost:7687")

with driver.session() as session:
    for query_variant in ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14a", "14b", "15", "16", "17", "18", "19", "20"]:
    #for query_variant in ["14a"]:
        query_num = int(re.sub("[^0-9]", "", query_variant))
        query_file = open(f'queries/bi-{query_num}.cypher', 'r')
        query_spec = query_file.read()

        parameters_csv = csv.DictReader(open(f'../parameters/bi-{query_variant}.csv'), delimiter='|')

        k = 0
        for query_parameters in parameters_csv:
            # convert fields based on type designators
            query_parameters = {k: int(v)                 if re.match('.*:(ID|LONG)', k) else v for k, v in query_parameters.items()}
            query_parameters = {k: convert_to_date(v)     if re.match('.*:DATE$', k)     else v for k, v in query_parameters.items()}
            query_parameters = {k: convert_to_datetime(v) if re.match('.*:DATETIME', k)  else v for k, v in query_parameters.items()}
            query_parameters = {k: v.split(';')           if re.findall('\[\]$', k)      else v for k, v in query_parameters.items()}
            # drop type designators
            type_pattern = re.compile(':.*')
            query_parameters = {type_pattern.sub('', k): v for k, v in query_parameters.items()}
            run_query(session, query_num, query_variant, query_spec, query_parameters)
            k += 1
            if k == 5:
                break

driver.close()
