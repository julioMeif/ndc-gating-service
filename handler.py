import os, json, datetime
import boto3

ddb = boto3.client('dynamodb')
CONFIG_TABLE   = os.environ['CONFIG_TABLE']
COUNTERS_TABLE = os.environ['COUNTERS_TABLE']

def _make_key(prov, route, trip, dep, ret):
    parts = [prov, route, trip, dep]
    if trip.upper()=='RT' and ret:
        parts.append(ret)
    parts.append(datetime.datetime.utcnow().strftime('%Y%m%d'))
    return "#".join(parts)

def check_ndc(event, context):
    b = json.loads(event.get('body', event))
    carriers, route, trip = b['carriers'], b['route'], b['tripType']
    dep, ret = b['departureDate'], b.get('returnDate')
    out = {}
    for prov in carriers:
        key = _make_key(prov, route, trip, dep, ret)
        cfg = ddb.get_item(TableName=CONFIG_TABLE,
                           Key={'provider':{'S':prov}}).get('Item')
        if not cfg:
            cfg = ddb.get_item(TableName=CONFIG_TABLE,
                               Key={'provider':{'S':'global'}})['Item']
        thresh, en = int(cfg['threshold']['N']), cfg['enabled']['BOOL']
        cnt = ddb.get_item(TableName=COUNTERS_TABLE,
                           Key={'pk':{'S':key}}).get('Item')
        fails = int(cnt['failCount']['N']) if cnt else 0
        out[prov] = {
          'allowNDC': en and fails < thresh,
          'failCount': fails,
          'threshold': thresh
        }
    return {'statusCode':200,'body':json.dumps(out)}

def increment_failures(event, context):
    b = json.loads(event.get('body', event))
    carriers, route, trip = b['carriers'], b['route'], b['tripType']
    dep, ret = b['departureDate'], b.get('returnDate')
    inc = int(b.get('increment',1))
    for prov in carriers:
        key = _make_key(prov, route, trip, dep, ret)
        ddb.update_item(
            TableName=COUNTERS_TABLE,
            Key={'pk':{'S':key}},
            UpdateExpression="ADD failCount :inc",
            ExpressionAttributeValues={':inc':{'N':str(inc)}})
    return {'statusCode':200,'body':json.dumps({'ok':True})}

def update_config(event, context):
    b = json.loads(event.get('body', event))
    ddb.put_item(TableName=CONFIG_TABLE, Item={
        'provider':  {'S': b['provider']},
        'threshold': {'N': str(b['threshold'])},
        'enabled':   {'BOOL': b['enabled']}
    })
    return {'statusCode':200,'body':json.dumps({'ok':True})}

