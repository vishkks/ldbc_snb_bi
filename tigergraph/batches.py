#!/usr/bin/python3
import argparse
import subprocess
from pathlib import Path
import time
import requests
from datetime import date, timedelta
import json
import os


VERTICES = ['Comment', 'Forum', 'Person', 'Post']
EDGES = ['Comment_hasCreator_Person', 'Comment_hasTag_Tag', 'Comment_isLocatedIn_Country',
    'Comment_replyOf_Comment', 'Comment_replyOf_Post', 'Forum_containerOf_Post',
    'Forum_hasMember_Person', 'Forum_hasModerator_Person', 'Forum_hasTag_Tag',
    'Person_hasInterest_Tag', 'Person_isLocatedIn_City', 'Person_knows_Person',
    'Person_likes_Comment', 'Person_likes_Post', 'Person_studyAt_University',
    'Person_workAt_Company', 'Post_hasCreator_Person', 'Post_hasTag_Tag',
    'Post_isLocatedIn_Country']
DEL_EDGES = ['Person_knows_Person', 'Person_likes_Comment', 'Person_likes_Post',
    'Forum_hasMember_Person']
NAMES = VERTICES + EDGES


def run_query(name, parameters, endpoint):
    HEADERS = {'GSQL-TIMEOUT': '36000000'}
    start = time.time()
    response = requests.get(f'{endpoint}/query/ldbc_snb/{name}', headers=HEADERS, params=parameters).json()
    end = time.time()
    duration = end - start
    return response['results'][0]['result'], duration

def load(job, data_dir, names, batch_dir, args):
    if args.cluster:
        load_by_gsql(job, data_dir, names, batch_dir)
    else:
        load_by_restpp(job, data_dir, names, batch_dir, args.endpoint)

"""
Load data using restpp endpoints
""" 
def load_by_restpp(job, data_dir, names, batch_dir, endpoint):
    for name in names:
        print(f'{name}:')
        folder = (data_dir/'dynamic'/name/batch_dir)
        if not folder.is_dir():
            print("!!! No changes occured")
            continue
        for f in folder.iterdir():
            print(f'- {f}')
            url = f'{endpoint}/ddl/ldbc_snb?tag={job}&filename=file_{name}&sep=%7C&ack=all'
            curl = f'curl -X POST -H "GSQL-TIMEOUT:3600000" --data-binary  @{f} "{url}"'
            res = subprocess.run(curl, shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            res = json.loads(res.stdout.decode("utf-8"))
            nlines = res["results"][0]["statistics"]["validLine"]
            print(f'> {nlines} changes')

"""
Load data using gsql command 
for concurrent insert/deletes on K8S cluster
""" 
def load_by_gsql(job, data_dir, names, batch_dir):
    gsql = f'RUN LOADING JOB {job} USING '
    gsql += ', '.join([f'file_{name}=\\"ANY:{data_dir}/dynamic/{name}/{batch_dir}\\"' for name in names])
    subprocess.run(f'gsql -g ldbc_snb {gsql}', shell=True)

def run_batch_update(batch_date, args):
    headers = {'GSQL-TIMEOUT': '36000000'}
    docker_data = Path('/data') if not args.cluster else args.data_dir
    batch_id = batch_date.strftime('%Y-%m-%d')
    batch_dir = f"batch_id={batch_id}"
    print(f"#################### {batch_dir} ####################")
    print("## Inserts")
    t0 = time.time()
    load(f'insert_vertex', args.data_dir/'inserts', VERTICES, batch_dir, args)
    load(f'insert_edge', args.data_dir/'inserts', EDGES, batch_dir, args)
    #tot_ins_time = time.time() - t0
    print("## Deletes")
    #t1 = time.time()
    for vertex in VERTICES:
        print(f"{vertex}:")
        path = args.data_dir/'deletes'/'dynamic'/vertex/batch_dir
        docker_path = docker_data/'deletes'/'dynamic'/vertex/batch_dir
        print(path)
        if not path.exists():
            continue
        for fp in path.glob('*.csv'):
            if fp.is_file():
                print(f'- {fp.name}')
                result, duration = run_query(f'del_{vertex}', {'file':str(docker_path/fp.name)}, args.endpoint)
                print(f'> {result} changes')
    #tot_del_time = time.time() - t1
    load(f'delete_edge', args.data_dir/'deletes', DEL_EDGES, batch_dir, args)
    print("\n## Rebuild")
    t0 = time.time()
    requests.get(f'{args.endpoint}/rebuildnow', headers=headers)
    print(f'Rebuild: {time.time()-t0} s')
    print("\n## Maintain materialized views ...")
    parameters = {"startDate": batch_date, "endDate": batch_date + timedelta(days=1)}
    queries = [f'cleanup_bi{q}' for q in [19,20]] + ['delta_root_post', 'delta_root_forum'] + [f'precompute_bi{q}' for q in [4,6,19,20]]
    for q in queries:
        print(f'{q}:\t', end='')
        t0 = time.time()
        requests.get(f'{args.endpoint}/query/ldbc_snb/{q}', params=parameters, headers=headers)
        requests.get(f'{args.endpoint}/rebuildnow', headers=headers) # wait for memory release
        print(f'{time.time()-t0:1.4f} s')
    return time.time() - t0

# main functions
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Batch updates for TigerGraph BI workloads')
    parser.add_argument('data_dir', type=Path, help='The directory to load data from')
    #parser.add_argument('--skip', action='store_true', help='skip precompute')
    parser.add_argument('--cluster', action='store_true', help='load concurrently on cluster')
    parser.add_argument('--endpoint', type=str, default = 'http://127.0.0.1:9000', help='tigergraph rest port')
    args = parser.parse_args()

    sf = os.environ.get("SF")
    output = Path('output')
    output.mkdir(exist_ok=True)
    timings_file = open(output/'timings.csv', 'w')
    timings_file.write(f'tool|sf|day|q|parameters|time\n')
    network_start_date = date(2012, 11, 29)
    network_end_date = date(2013, 1, 1)
    batch_date = network_start_date
    batch_size = timedelta(days=1)
    while batch_date < network_end_date:
        write_time = run_batch_update(batch_date, args)
        timings_file.write(f'TigerGraph|{sf}|{batch_date}|writes||{write_time:.6f}\n')
        timings_file.flush()
        batch_date = batch_date + batch_size
