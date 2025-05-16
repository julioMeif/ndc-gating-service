import os, json, datetime
import boto3

ddb = boto3.client('dynamodb')
CONFIG_TABLE   = os.environ['CONFIG_TABLE']
COUNTERS_TABLE = os.environ['COUNTERS_TABLE']

def _make_key(prov, route, trip, dep, ret):
    parts = [prov, route, trip, dep]
    if trip.upper() == 'RT' and ret:
        parts.append(ret)
    parts.append(datetime.datetime.utcnow().strftime('%Y%m%d'))
    return "#".join(parts)

def check_ndc(event, context):
    raw = event.get('body')
    if not raw:
        return {'statusCode':400, 'body': json.dumps({'error':'Missing JSON body'})}
    try:
        body = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError:
        return {'statusCode':400, 'body': json.dumps({'error':'Invalid JSON'})}

    carriers = body.get('carriers', [])
    route    = body.get('route')
    trip     = body.get('tripType')
    dep      = body.get('departureDate')
    ret      = body.get('returnDate')

    if not (carriers and route and trip and dep):
        return {'statusCode':400, 
                'body': json.dumps({'error':'carriers, route, tripType and departureDate are required'})}

    results = {}
    for prov in carriers:
        key = _make_key(prov, route, trip, dep, ret)

        # 1) Try provider config
        resp = ddb.get_item(TableName=CONFIG_TABLE, Key={'provider':{'S':prov}})
        print(f"DEBUG: get_item for provider={prov}: {resp!r}")
        cfg = resp.get('Item')
        # 2) Fallback to global
        if not cfg:
            resp = ddb.get_item(TableName=CONFIG_TABLE, Key={'provider':{'S':'global'}})
            print(f"DEBUG: get_item for provider={prov}: {resp!r}")
            cfg = resp.get('Item')
        if not cfg:
            return {
                'statusCode':500,
                'body': json.dumps({'error':f'No config found for provider {prov} or global'}) 
            }

        threshold = int(cfg['threshold']['N'])
        enabled   = cfg['enabled']['BOOL']

        # 3) Read today’s failure count
        cnt_resp = ddb.get_item(TableName=COUNTERS_TABLE, Key={'pk':{'S':key}})
        cnt_item = cnt_resp.get('Item')
        fails    = int(cnt_item['failCount']['N']) if cnt_item else 0

        results[prov] = {
            'allowNDC': enabled and (fails < threshold),
            'failCount': fails,
            'threshold': threshold
        }

    return {'statusCode':200, 'body': json.dumps(results)}

def increment_failures(event, context):
    raw = event.get('body')
    try:
        body = json.loads(raw) if isinstance(raw, str) else raw
    except:
        return {'statusCode':400, 'body': json.dumps({'error':'Invalid JSON'})}

    carriers = body.get('carriers', [])
    route    = body.get('route')
    trip     = body.get('tripType')
    dep      = body.get('departureDate')
    ret      = body.get('returnDate')
    inc      = int(body.get('increment', 1))

    for prov in carriers:
        key = _make_key(prov, route, trip, dep, ret)
        ddb.update_item(
            TableName=COUNTERS_TABLE,
            Key={'pk':{'S':key}},
            UpdateExpression="ADD failCount :inc",
            ExpressionAttributeValues={':inc':{'N':str(inc)}}
        )

    return {'statusCode':200, 'body': json.dumps({'ok':True})}

def update_config(event, context):
    raw = event.get('body')
    try:
        body = json.loads(raw) if isinstance(raw, str) else raw
    except:
        return {'statusCode':400, 'body': json.dumps({'error':'Invalid JSON'})}

    provider  = body.get('provider')
    threshold = body.get('threshold')
    enabled   = body.get('enabled')

    if provider is None or threshold is None or enabled is None:
        return {'statusCode':400, 'body': json.dumps({'error':'provider, threshold, enabled are required'})}

    ddb.put_item(
        TableName=CONFIG_TABLE,
        Item={
            'provider':  {'S': provider},
            'threshold': {'N': str(threshold)},
            'enabled':   {'BOOL': enabled}
        }
    )
    return {'statusCode':200, 'body': json.dumps({'ok':True})}
