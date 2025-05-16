import argparse
import os
import warnings

from datetime import datetime

import requests

from elasticsearch import Elasticsearch

warnings.filterwarnings("ignore")

ES_HOST = f"https://{os.getenv('ELASTICSEARCH_HOST')}:{os.getenv('ELASTICSEARCH_PORT')}"
ES_USERNAME_PASSWORD = "elastic:elastic"
# https://www.elastic.co/docs/api/doc/elasticsearch/operation/operation-reindex
REINDEX_ENDPOINT = f"{ES_HOST}/_reindex"

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dest-index", default="metrics-apm.app.all-default")
    parser.add_argument("--pattern", type=str, default="metrics-apm.app.*")
    parser.add_argument("--conflict-decision", type=str, default="abort")
    args = parser.parse_args()
    dest_index = args.dest_index
    pattern = args.pattern
    conflict_decision = args.conflict_decision

    es_client = Elasticsearch(hosts=ES_HOST, basic_auth=tuple(ES_USERNAME_PASSWORD.split(":")), verify_certs=False)
    response = es_client.indices.get_data_stream(name=pattern)
    valid_data_stream_names = [ds["name"] for ds in response["data_streams"] if ds["name"] != dest_index]

    strategy = {
        "conflicts": conflict_decision,
        "source": {
            "index": valid_data_stream_names,
        },
        "dest": {
            "op_type": "create",
            "index": dest_index,
        },
    }

    print("Migrating indices...")
    credentials = tuple(ES_USERNAME_PASSWORD.split(":"))
    resp = requests.post(REINDEX_ENDPOINT, json=strategy, auth=credentials, verify=False)
    if resp.status_code != 200:
        print(f"ES returned status code {resp.status_code} including the following details: {resp.text}")
        exit(1)

    print("Number of data streams to be deleted:", len(valid_data_stream_names))
    count = 0
    for data_stream_to_be_deleted in valid_data_stream_names:
        es_client.indices.delete_data_stream(name=data_stream_to_be_deleted)
        count += 1
        if count % 25 == 0:
            print(f"Deleted {count} data streams...")

    print("Done!")
