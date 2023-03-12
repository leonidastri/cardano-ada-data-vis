from django.shortcuts import render
from cardanopools.dbquery  import *
import json, requests, datetime
from decimal import *
import statistics
import numpy as np

EPOCHSLOTS = 432000
MILLION = 1000000
BILLION = 1000000000

def index(request):

    # Get usd price from coingecko.com
    response = requests.get('https://api.coingecko.com/api/v3/coins/cardano')
    json_data = json.loads(response.text)
    price = json_data['market_data']['current_price']['usd']

    # Get total transactions
    sqlQuery = "SELECT count(id) AS total_count, sum(out_sum) AS total_amount FROM tx;"
    totalTransactions = execute_query(sqlQuery)
    totalTransactionsCount = totalTransactions[0]['total_count']
    totalTransactionsAmount = totalTransactions[0]['total_amount']
    totalTransactionsCount = totalTransactionsCount
    totalTransactionsAmount = round(totalTransactionsAmount/BILLION,2)
    
    # Get current epoch
    sqlQuery = "SELECT MAX (epoch_no) as epoch_no FROM block;"
    currentEpoch = execute_query(sqlQuery)
    currentEpochNo = currentEpoch[0]['epoch_no']

    # Get current slot
    sqlQuery = "SELECT slot_no FROM block WHERE block_no IS NOT NULL ORDER BY block_no DESC LIMIT 1;"
    currentSlot = execute_query(sqlQuery)

    currentSlot = currentSlot[0]['slot_no']
    currentSlot = currentSlot%EPOCHSLOTS
    epochProgress = currentSlot/EPOCHSLOTS * 100

    # Get live pools
    sqlQuery = "SELECT COUNT(*) FROM live_pool;"
    currentPools = execute_query(sqlQuery)
    currentPools = currentPools[0]['count']

    # Get live delegators
    sqlQuery = "SELECT COUNT(*) FROM live_delegation;"
    delegators = execute_query(sqlQuery)
    delegators = delegators[0]['count']

    # Get live pool owners
    sqlQuery = "SELECT COUNT(*) FROM live_pool_owner;"
    poolOwners = execute_query(sqlQuery)
    poolOwners = poolOwners[0]['count']

    # Get current supply
    sqlQuery = "SELECT * FROM current_supply;"
    currentSupply = execute_query(sqlQuery)[0]['current_supply']

    # Get live stake
    sqlQuery = "SELECT sum(stake) as stake FROM live_stake;"
    liveStake = execute_query(sqlQuery)[0]['stake']

    # Get latest blocks
    sqlQuery = "select encode(block.hash::bytea, 'hex'), block.block_no, block.epoch_no, block.slot_no, block.\"time\" as time, block.tx_count, encode(pool_hash.hash_raw::bytea, 'hex') as pool_hash, pool_offline_data.metadata as pool_metadata from block inner join slot_leader on block.slot_leader_id = slot_leader.id inner join pool_hash on slot_leader.pool_hash_id = pool_hash.id inner join pool_offline_data on pool_hash.id = pool_offline_data.pool_id inner join pool_update on pool_update.hash_id = slot_leader.pool_hash_id and pool_update.id = (select max(id) from pool_update as pu where pu.hash_id = slot_leader.pool_hash_id) inner join pool_metadata_ref on pool_update.meta_id = pool_metadata_ref.id order by block.\"time\" desc limit 5;"
    latestBlocksResult = execute_query(sqlQuery)
    latestBlocks = []
    i = 0
    for block in latestBlocksResult:
        i = i + 1
        temp = {}
        temp['epoch_no'] = block['epoch_no']
        temp['slot_no'] = block['slot_no']
        temp['time'] = datetime.datetime.strftime(block['time'], '%Y-%m-%d %H:%M:%S')
        temp['block_hash_start'] = block['encode'][3:7]
        temp['block_hash_end'] = block['encode'][-4:]
        temp['block_hash'] = block['encode'][3:]
        temp['tx_count'] = block['tx_count']
        temp['pool_hash'] = block['pool_hash']
        temp['pool_metadata'] = json.loads(block['pool_metadata'])
        temp['slot_leader'] = "[" + temp['pool_metadata']['ticker'] + "] " + temp['pool_metadata']['name']
        temp['homepage'] = temp['pool_metadata']['homepage']
        latestBlocks.append(temp)

    # Get latest snapshot's epoch
    sqlQuery = "SELECT MAX (epoch_no) AS epoch_no FROM epoch_stake;"
    lsEpoch = execute_query(sqlQuery)
    lsEpochNo = lsEpoch[0]['epoch_no']

    # LGet latest snapshot's epoch pools
    params = [lsEpochNo]
    sqlQuery = "select encode(pool_hash.hash_raw::bytea, 'hex') as hash_raw_hex, pool_hash.view, latest_pool_data.metadata as pool_metadata from epoch_pools left join latest_pool_data on latest_pool_data.pool_id = epoch_pools.pool_id inner join pool_hash on pool_hash.id = epoch_pools.pool_id where epoch_pools.epoch_no = %s;"
    poolsLsResult = execute_query_params(sqlQuery,params)
    poolsLs = []
    i = 0
    for pool in poolsLsResult:
        i = i + 1
        temp = {}
        temp['pool_view'] = pool['view']
        temp['pool_hash'] = pool['hash_raw_hex']
        if pool['pool_metadata'] is not None:
            temp['pool_metadata'] = json.loads(pool['pool_metadata'], strict=False)
            temp['pool'] = "[" + temp['pool_metadata']['ticker'] + "] " + temp['pool_metadata']['name']
            temp['pool_page'] = temp['pool_metadata']['homepage']
        poolsLs.append(temp)
    
    return render(request, 'cardanopools/index.html', {
        'price': f"{price:,}",
        'totalTransactionsCount': f"{totalTransactionsCount:,}",
        'totalTransactionsAmount': f"{totalTransactionsAmount:,}",
        'currentEpoch': currentEpochNo,
        'lsEpochNo': lsEpochNo,
        'currentSlot': f"{currentSlot:,}",
        'currentSupply': f"{round(currentSupply/BILLION,2):,}",
        'liveStake': f"{round(liveStake/BILLION,2):,}",
        'epochProgress': int(epochProgress),
        'epochSlots': f"{EPOCHSLOTS:,}",
        'delegators': f"{delegators:,}",
        'poolOwners': f"{poolOwners:,}",
        'currentPools': f"{currentPools:,}",
        'latestBlocks': latestBlocks,
        'poolsLs': poolsLs,
        })

# Pool description
def pool(request,pool_hash):

    # Get latest snapshot's epoch
    sqlQuery = "SELECT MAX (epoch_no) AS epoch_no FROM epoch_stake;"
    lsEpoch = execute_query(sqlQuery)
    lsEpochNo = lsEpoch[0]['epoch_no']

    # Get pool information
    sqlQuery = "select pool_hash.id, pool_hash.view as pool_view, latest_pool_data.metadata as pool_metadata from epoch_pools inner join pool_hash on pool_hash.id = epoch_pools.pool_id left join latest_pool_data on pool_hash.id = latest_pool_data.pool_id where pool_hash.hash_raw = decode(%s, 'hex');"
    params = [pool_hash]
    poolResult = execute_query_params(sqlQuery,params)
    pool_id = poolResult[0]['id']
    poolInfo = {}
    poolInfo['pool_hash'] = pool_hash
    poolInfo['pool_view'] = poolResult[0]['pool_view']

    # If metadata exist for this pool
    if poolResult[0]['pool_metadata'] is not None:
        poolInfo['pool_metadata'] = json.loads(poolResult[0]['pool_metadata'], strict=False)
        poolInfo['pool'] = "[" + poolInfo['pool_metadata']['ticker'] + "] " + poolInfo['pool_metadata']['name']
        poolInfo['description'] = poolInfo['pool_metadata']['description']
        poolInfo['ticker'] = poolInfo['pool_metadata']['ticker']
        poolInfo['homepage'] = poolInfo['pool_metadata']['homepage']
    else:
        poolInfo['nopage'] = 'n/a'

    params = [pool_id]

    # Get pool's delegators
    sqlQuery = "SELECT encode(stake_address.hash_raw::bytea, 'hex') as hash_raw, stake_address.view, epoch_stake.amount/1000000 as stake FROM stake_address INNER JOIN epoch_stake ON stake_address.id = epoch_stake.addr_id INNER JOIN pool_hash on pool_hash.id = epoch_stake.pool_id WHERE epoch_stake.epoch_no = ( SELECT max(epoch_no) FROM epoch_stake) and pool_hash.id = %s;"
    delegatorsResult = execute_query_params(sqlQuery,params)
    delegatorsCount = len(delegatorsResult)
    delegators = []
    
    i = 0
    # Get information about each delegator
    for delegator in delegatorsResult:
        i = i + 1
        temp = {}
        temp['hash_raw'] = delegator['hash_raw']
        temp['view'] = delegator['view']
        temp['stake'] = round(delegator['stake'],2)
        temp['identifier'] = i
        delegators.append(temp)

    # Get pool owners
    sqlQuery = "SELECT encode(stake_address.hash_raw::bytea, 'hex') as hash_raw, stake_address.view FROM live_pool_owner INNER JOIN stake_address ON stake_address.id = live_pool_owner .addr_id WHERE live_pool_owner.pool_hash_id = %s;"
    poolOwnersResult = execute_query_params(sqlQuery,params)

    poolOwners = []
    i = 0
    # Get information about each pool owner [1 or more pool owners]
    for poolOwner in poolOwnersResult:
        i = i + 1
        temp = {}
        temp['hash_raw'] = poolOwner['hash_raw']
        temp['view'] = poolOwner['view']
        poolOwners.append(temp)

    params = [pool_id,lsEpochNo]
    # Get total stake of pool
    sqlQuery = "SELECT stake FROM epoch_pool_stake WHERE pool_id = %s and epoch_no = %s"
    poolStakeResult = execute_query_params(sqlQuery,params)
    totalStake = poolStakeResult[0]['stake']

    # Get total pledge of pool
    sqlQuery = "SELECT pledge FROM epoch_pool_pledge WHERE pool_id = %s and epoch_no = %s"
    poolStakeResult = execute_query_params(sqlQuery,params)
    totalPledge = poolStakeResult[0]['pledge']

    if 'ticker' in poolInfo:
        params = [pool_id,poolInfo['ticker'],poolInfo['ticker'],poolInfo['ticker']]
    else:
        params = [pool_id,'','','']
    
    # Get leverage of pool per epoch (It may be a single pool or it may be member of a group of pools)
    sqlQuery = "(SELECT leverage, epoch_no FROM epoch_leverage_no_group where pool_id = %s) UNION ALL (select leverage, epoch_no from epoch_leverage_group_3 where prefix = substring(%s,0,4)) UNION ALL (select leverage, epoch_no from epoch_leverage_group_4 where prefix = substring(%s,0,5)) UNION ALL (select leverage, epoch_no from epoch_leverage_group_5 where prefix = %s ) ORDER BY epoch_no ASC"
    epochLeverages = execute_query_params(sqlQuery,params)

    leverages = []
    labels = []
    for epochLeverage in epochLeverages:
        leverages.append(str(float(round(epochLeverage['leverage'],2))))
        labels.append(str(epochLeverage['epoch_no']))

    labels = ','.join(labels)
    data = ','.join(leverages)

    return render(request, 'cardanopools/pool.html', {
        'delegators': delegators,
        'delegatorsCount': delegatorsCount,
        'poolOwners': poolOwners,
        'pool': poolInfo,
        'totalStake': round(totalStake,2),
        'totalPledge': round(totalPledge,2),
        'labels': labels,
        'data': data,
    })

# Stake address description
def stake(request,stake_hash):

    # Get usd price from coingecko.com
    response = requests.get('https://api.coingecko.com/api/v3/coins/cardano')
    json_data = json.loads(response.text)
    price = json_data['market_data']['current_price']['usd']

    # Get stake address
    sqlQuery = "SELECT id, encode(hash_raw::bytea, 'hex') as hash_raw, view FROM stake_address WHERE hash_raw = decode(%s, 'hex');"
    params = [stake_hash]
    stakeAddress = execute_query_params(sqlQuery,params)

    # Get addresses and balances connected to a stake address (UTxOs)
    sqlQuery = "SELECT tx_outer.address AS addr, SUM(tx_outer.value)/1000000 AS balance FROM tx_out as tx_outer INNER JOIN stake_address ON stake_address.id = tx_outer.stake_address_id WHERE NOT EXISTS ( SELECT tx_out.id FROM tx_out INNER JOIN tx_in ON tx_out.tx_id = tx_in.tx_out_id AND tx_out.index = tx_in.tx_out_index WHERE tx_outer.id = tx_out.id) AND stake_address.id = %s GROUP BY tx_outer.address;"
    params = [stakeAddress[0]['id']]
    utxosAddressResult = execute_query_params(sqlQuery,params)
    
    utxosAddresses = []
    i = 0
    for utxosAddress in utxosAddressResult:
        i = i + 1
        temp = {}
        temp['address'] = utxosAddress['addr']
        temp['balance'] = round(utxosAddress['balance'],2)
        temp['usdbalance'] = round(utxosAddress['balance'] * Decimal(price),2)
        utxosAddresses.append(temp)

    # Get rewards of stake address
    sqlQuery = "SELECT encode(pool_hash.hash_raw::bytea, 'hex') as pool_hash_raw, reward.epoch_no, reward.amount/1000000 as amount, latest_pool_data.metadata as pool_metadata FROM reward INNER JOIN latest_pool_data ON reward.pool_id = latest_pool_data.pool_id INNER JOIN pool_hash ON pool_hash.id = reward.pool_id WHERE addr_id = %s ORDER BY epoch_no ASC;"
    params = [stakeAddress[0]['id']]
    rewardResult = execute_query_params(sqlQuery,params)
    
    rewards = []
    labels = []
    data = []
    i = 0

    for reward in rewardResult:
        i = i + 1
        temp = {}
        temp['epoch_no'] = reward['epoch_no']
        labels.append(str(temp['epoch_no']))
        temp['amount'] = round(reward['amount'],2)
        temp['usdamount'] = round(reward['amount'] * Decimal(price),2)

        data.append(str(temp['amount']))
        if reward['pool_metadata'] is not None:
            temp['pool_metadata'] = json.loads(reward['pool_metadata'], strict=False)
            temp['pool'] = "[" + temp['pool_metadata']['ticker'] + "] " + temp['pool_metadata']['name']
            temp['pool_hash_raw'] = reward['pool_hash_raw']
        else:
            temp['nopool'] = 'n/a'
        rewards.append(temp)

    labels = ','.join(labels)
    data = ','.join(data)

    return render(request, 'cardanopools/stake.html', {
        'stakeAddress': stakeAddress[0],
        'utxosAddresses': utxosAddresses,
        'rewards': rewards,
        'labels': labels,
        'data': data,
    })

# Live leverage
def liveleverage(request):

    poolsLiveLeverage = []

    # Get leverage of live pools in groups with ticker prefix of 3 characters length
    sqlQuery = "select view, leverage, metadata from group_3_ids inner join pool_hash on pool_id = id inner join live_leverage_group_3 on group_3_ids.prefix = live_leverage_group_3.prefix left join latest_pool_data pld on pld.pool_id = group_3_ids.pool_id where epoch_no = (select max(epoch_no) from epoch_stake);"
    group3Result = execute_query(sqlQuery)

    for pool in group3Result:
        temp = {}
        temp['pool_view'] = pool['view']
        temp['leverage'] = round(pool['leverage'],2)
        if pool['metadata'] is not None:
            temp['pool_metadata'] = json.loads(pool['metadata'], strict=False)
            temp['pool'] = "[" + temp['pool_metadata']['ticker'] + "] " + temp['pool_metadata']['name']
        poolsLiveLeverage.append(temp)

    # Get leverage of live pools in groups with ticker prefix of 4 characters length
    sqlQuery = "select view, leverage, metadata from group_4_ids inner join pool_hash on pool_id = id inner join live_leverage_group_4 on group_4_ids.prefix = live_leverage_group_4.prefix left join latest_pool_data pld on pld.pool_id = group_4_ids.pool_id where epoch_no = (select max(epoch_no) from epoch_stake);"
    group4Result = execute_query(sqlQuery)
    
    for pool in group4Result:
        temp = {}
        temp['pool_view'] = pool['view']
        temp['leverage'] = round(pool['leverage'],2)
        if pool['metadata'] is not None:
            temp['pool_metadata'] = json.loads(pool['metadata'], strict=False)
            temp['pool'] = "[" + temp['pool_metadata']['ticker'] + "] " + temp['pool_metadata']['name']
        poolsLiveLeverage.append(temp)

    # Get leverage of live pools in groups with ticker prefix of 5 characters length
    sqlQuery = "select view, leverage, metadata from group_5_ids inner join pool_hash on pool_id = id inner join live_leverage_group_5 on group_5_ids.prefix = live_leverage_group_5.prefix left join latest_pool_data pld on pld.pool_id = group_5_ids.pool_id where epoch_no = (select max(epoch_no) from epoch_stake);"
    group5Result = execute_query(sqlQuery)

    for pool in group5Result:
        temp = {}
        temp['pool_view'] = pool['view']
        temp['leverage'] = round(pool['leverage'],2)
        if pool['metadata'] is not None:
            temp['pool_metadata'] = json.loads(pool['metadata'], strict=False)
            temp['pool'] = "[" + temp['pool_metadata']['ticker'] + "] " + temp['pool_metadata']['name']
        poolsLiveLeverage.append(temp)

    # Get leverage of live single pools
    sqlQuery = "select view, leverage, metadata from live_leverage_no_group inner join pool_hash on pool_id = id left join latest_pool_data lpd on lpd.pool_id = live_leverage_no_group.pool_id;"
    noGroupResult = execute_query(sqlQuery)

    for pool in noGroupResult:
        temp = {}
        temp['pool_view'] = pool['view']
        temp['leverage'] = round(pool['leverage'],2)
        if pool['metadata'] is not None:
            temp['pool_metadata'] = json.loads(pool['metadata'], strict=False)
            temp['pool'] = "[" + temp['pool_metadata']['ticker'] + "] " + temp['pool_metadata']['name']
        poolsLiveLeverage.append(temp)

    return render(request, 'cardanopools/live-leverage.html', {
        'poolsLiveLeverage': poolsLiveLeverage,
    })

# Leverage per epoch
def leverageperepoch(request):

    # Get minimum and maximum epoch
    sqlQuery = "SELECT MIN(epoch_no) as min_epoch, MAX(epoch_no) max_epoch FROM epoch_stake;"
    result = execute_query(sqlQuery)
    min_epoch = result[0]['min_epoch']
    max_epoch = result[0]['max_epoch']

    labels = []
    medianLeveragePerEpoch = []
    q1LeveragePerEpoch = []
    q3LeveragePerEpoch = []
    medianPledgePerEpoch = []
    medianStakePerEpoch = []

    # For each epoch from minimum to maximum epoch
    for epoch in range(min_epoch,max_epoch+1):
        params = [epoch, epoch, epoch, epoch]

        # Find every leverage [leverage of single pools and leverage of groups of pools]
        sqlQuery = "(SELECT leverage,epoch_no FROM epoch_leverage_no_group WHERE epoch_no = %s) UNION ALL (select leverage, epoch_no from epoch_leverage_group_3 where epoch_no = %s) UNION ALL (select leverage, epoch_no from epoch_leverage_group_4 where epoch_no = %s) UNION ALL (select leverage, epoch_no from epoch_leverage_group_5 where epoch_no = %s) ORDER BY leverage ASC;"
        epochLeverage = execute_query_params(sqlQuery,params)

        leverages = []
        for leverage in epochLeverage:
            leverages.append(float(round(leverage['leverage'],2)))

        # Compute median leverage per epoch
        medianLeveragePerEpoch.append(str(statistics.median(leverages)))
        # Compute 25th percentile leverage per epoch
        q1LeveragePerEpoch.append(str(np.percentile(leverages, 25, interpolation = 'midpoint')))
        # Compute 75th percentile leverage per epoch
        q3LeveragePerEpoch.append(str(np.percentile(leverages, 75, interpolation = 'midpoint')))

        labels.append(str(leverage['epoch_no']))

        # Get total pledge of sinle pools and group of pools
        sqlQuery = "(SELECT total_pledge as pledge FROM epoch_group_3_pledge WHERE epoch_no = %s) UNION ALL (SELECT total_pledge as pledge FROM epoch_group_4_pledge WHERE epoch_no = %s) UNION ALL (SELECT total_pledge as pledge FROM epoch_group_5_pledge WHERE epoch_no = %s) UNION ALL (SELECT pledge FROM epoch_pool_pledge_no_iog epp WHERE epoch_no = %s AND  not exists (select true from group_3_ids g where epoch_no = epp.epoch_no and pool_id = epp.pool_id) and not exists (select true from group_4_ids g where epoch_no = epp.epoch_no and pool_id = epp.pool_id) and not exists (select true from group_5_ids g where epoch_no = epp.epoch_no and pool_id = epp.pool_id)) ORDER BY pledge ASC"
        epochPledge = execute_query_params(sqlQuery,params)

        pledges = []
        for pledge in epochPledge:
            pledges.append(float(round(pledge['pledge'],2)/MILLION))

        # Get median total pledge
        medianPledgePerEpoch.append(str(statistics.median(pledges)))

        # Get total stake of single pools and group of pools
        sqlQuery = "(SELECT total_stake as stake FROM epoch_group_3_stake WHERE epoch_no = %s) UNION ALL (SELECT total_stake as stake FROM epoch_group_4_stake WHERE epoch_no = %s) UNION ALL (SELECT total_stake as stake FROM epoch_group_5_stake WHERE epoch_no = %s) UNION ALL (SELECT stake FROM epoch_pool_stake_no_iog eps WHERE epoch_no = %s AND  not exists (select true from group_3_ids g where epoch_no = eps.epoch_no and pool_id = eps.pool_id) and not exists (select true from group_4_ids g where epoch_no = eps.epoch_no and pool_id = eps.pool_id) and not exists (select true from group_5_ids g where epoch_no = eps.epoch_no and pool_id = eps.pool_id)) ORDER BY stake ASC"
        epochStake = execute_query_params(sqlQuery,params)

        stakes = []
        for stake in epochStake:
            stakes.append(float(round(stake['stake'],2)/BILLION))

        # Get median total stake
        medianStakePerEpoch.append(str(statistics.median(stakes)))

    labels = ','.join(labels)
    data1 = ','.join(medianLeveragePerEpoch)
    data2 = ','.join(q1LeveragePerEpoch)
    data3 = ','.join(q3LeveragePerEpoch)
    data6 = ','.join(medianPledgePerEpoch)
    data7 = ','.join(medianStakePerEpoch)

    # Get over-saturated pools after epoch 234. (Over-saturated pools contain more than 64 million ADA)
    sqlQuery = "select count(*), epoch_no from epoch_pool_stake where stake > 64000000 and epoch_no >= 234 group by epoch_no order by epoch_no;"
    overSaturatedPoolsCountResult = execute_query(sqlQuery)

    labels2 = []
    overSaturatedPoolsPerEpoch = []
    for overSaturatedPoolsCount in overSaturatedPoolsCountResult:
        labels2.append(str(overSaturatedPoolsCount['epoch_no']))
        overSaturatedPoolsPerEpoch.append(str(overSaturatedPoolsCount['count']))

    labels2 = ','.join(labels2[1:])
    data4 = ','.join(overSaturatedPoolsPerEpoch)

    # Get ratio between total pools in groups and total pools per epoch
    poolsInGroupsPerEpoch = []
    # For each epoch, find total pools in groups
    for epoch in range(min_epoch,max_epoch+1):
        params = [epoch]
        poolsSum = 0

        sqlQuery = "select count(*) from group_3_ids where epoch_no = %s group by epoch_no;"
        group3PoolsCountResult = execute_query_params(sqlQuery,params)

        for group3 in group3PoolsCountResult:
            poolsSum += group3['count']

        sqlQuery = "select count(*) from group_4_ids where epoch_no = %s group by epoch_no;"
        group4PoolsCountResult = execute_query_params(sqlQuery,params)

        for group4 in group4PoolsCountResult:
            poolsSum += group4['count']

        sqlQuery = "select count(*) from group_5_ids where epoch_no = %s group by epoch_no;"
        group5PoolsCountResult = execute_query_params(sqlQuery,params)

        for group5 in group5PoolsCountResult:
            poolsSum += group5['count']

        poolsInGroupsPerEpoch.append(poolsSum)

    # Get total pools per epoch
    sqlQuery = "select * from total_epoch_pools order by epoch_no;"
    poolsPerEpochResult = execute_query_params(sqlQuery,params)

    poolsPerEpoch = []
    for total_pools in poolsPerEpochResult:
            poolsPerEpoch.append(total_pools['amount'])
    
    # Compute ratio between total pools in groups and total pools per epoch
    percentageOfPoolsInGroups = [str(a/b) for a,b in zip(poolsInGroupsPerEpoch,poolsPerEpoch)]
    data5 = ','.join(percentageOfPoolsInGroups)

    # Median leverage per epoch using only pools before 234 for every epoch
    # medianLeveragePerEpoch234 = []
    # for epoch in range(min_epoch,max_epoch+1):
    #     params = [epoch, epoch, epoch, epoch]
    #     sqlQuery = "(SELECT leverage,epoch_no FROM epoch_leverage_no_group_234 WHERE epoch_no = %s) UNION ALL (select leverage, epoch_no from epoch_leverage_group_3_234 where epoch_no = %s) UNION ALL (select leverage, epoch_no from epoch_leverage_group_4_234 where epoch_no = %s) UNION ALL (select leverage, epoch_no from epoch_leverage_group_5_234 where epoch_no = %s) ORDER BY leverage ASC;"
    #     epochLeverage234 = execute_query_params(sqlQuery,params)

    #     leverages = []
    #     for leverage in epochLeverage234:
    #         leverages.append(float(round(leverage['leverage'],2)))

    #     #print(leverages)
    #     medianLeveragePerEpoch234.append(str(statistics.median(leverages)))
    # data8 = ','.join(medianLeveragePerEpoch234)

    return render(request, 'cardanopools/leverage-per-epoch.html', {
        'labels': labels,
        'data1': data1,
        'data2': data2,
        'data3': data3,
        'labels2': labels2,
        'data4': data4,
        'data5': data5,
        'data6': data6,
        'data7': data7,
        # 'data8': data8,
    })

# 51% Attack
def attack51(request):

    data1 = []
    data2 = []
    data3 = []
    
    # Get total Supply
    sqlQuery = "SELECT current_supply FROM current_supply;"
    totalSupply = execute_query(sqlQuery)[0]['current_supply']

    # Get latest epoch
    sqlQuery = "SELECT max(epoch_no) as max_epoch FROM epoch_stake;"
    maxEpoch = execute_query(sqlQuery)[0]['max_epoch']

    params = [maxEpoch]
    
    # Get total stake of each pool [epoch stake from latest snapshot]
    sqlQuery = "SELECT SUM(amount)/1000000 AS amount FROM epoch_stake WHERE epoch_no =  %s GROUP BY pool_id ORDER BY amount DESC"
    stakePerPool = execute_query_params(sqlQuery,params)

    poolCount = 0
    running_stake = 0
    # Compute how many pools have more than 50% of current total supply [epoch stake from latest snapshot]
    for poolStake in stakePerPool:
        poolCount += 1
        running_stake += poolStake['amount']
        if running_stake > Decimal(0.50) * totalSupply:
            break

    data1.append(str(poolCount))

    # Get total stake of each pool [live_stake]
    sqlQuery = "SELECT sum(stake) as stake FROM live_stake GROUP BY pool_id ORDER BY stake DESC"
    stakePerPool = execute_query_params(sqlQuery,params)

    poolCount = 0
    running_stake = 0
    # Compute how many pools have more than 50% of current total supply [live stake]
    for poolStake in stakePerPool:
        poolCount += 1
        running_stake += poolStake['stake']
        if running_stake > Decimal(0.50) * totalSupply:
            break

    data1.append(str(poolCount))


    # Get total stake of each stake address [epoch stake from latest snapshot]
    sqlQuery = "SELECT amount/1000000 AS amount FROM epoch_stake WHERE epoch_no = %s ORDER BY amount DESC"
    stakePerWallet = execute_query_params(sqlQuery,params)

    stakeAddressCount = 0
    running_stake = 0
    # Compute how many stake addresses have more than 50% of current total supply [epoch stake from latest snapshot]
    for walletStake in stakePerWallet:
        stakeAddressCount += 1
        running_stake += walletStake['amount']
        if running_stake > Decimal(0.50) * totalSupply:
            break

    data2.append(str(stakeAddressCount))

    # Get total stake of each stake address [live_stake]
    sqlQuery = "SELECT stake FROM live_stake ORDER BY stake DESC"
    stakePerWallet = execute_query(sqlQuery)

    stakeAddressCount = 0
    running_stake = 0
    # Compute how many stake addresses have more than 50% of current total supply [live stake]
    for walletStake in stakePerWallet:
        stakeAddressCount += 1
        running_stake += walletStake['stake']
        if running_stake >= Decimal(0.51) * totalSupply:
            break

    data2.append(str(stakeAddressCount))

    # Get total stake of each address [live_stake]
    sqlQuery = "SELECT balance FROM richest_address ORDER BY balance DESC"
    addressBalance = execute_query(sqlQuery)

    addressCount = 0
    running_stake = 0
    # Compute how many addresses have more than 50% of current total supply [live stake]
    for address in addressBalance:
        addressCount += 1
        running_stake += address['balance']
        if running_stake >= Decimal(0.51) * totalSupply:
            break

    data3.append(str(addressCount))

    labels1 = ','.join(["latest snapshot pools","live pools"])
    data1 = ','.join(data1)
    labels2 = ','.join(["latest snapshot stake address","live stake address"])
    data2 = ','.join(data2)
    data3 = ','.join(data3)
    
    return render(request, 'cardanopools/attack51.html', {
        'labels1': labels1,
        'labels2': labels2,
        'data1': data1,
        'data2': data2,
        'data3': data3,
    })

# Other epoch statistics
def epochstatistics(request):

    # Get total rewards per epoch
    sqlQuery = "SELECT * FROM total_epoch_rewards;"
    rewardsResult = execute_query(sqlQuery)
    
    # Get total stake per epoch
    sqlQuery = "SELECT * FROM total_epoch_stake order by epoch_no ASC;"
    totalStakesResult = execute_query(sqlQuery)

    # Get total pledge per epoch
    sqlQuery = "SELECT * FROM total_epoch_pledge order by epoch_no ASC;"
    totalPledgeResult = execute_query(sqlQuery)

    # Get total pools per epoch
    sqlQuery = "SELECT * FROM total_epoch_pools;"
    totalPoolsResult = execute_query(sqlQuery)

    # Get total delegators per epoch
    sqlQuery = "select count(*) as amount, epoch_no from epoch_stake group by epoch_no ORDER BY epoch_no ASC;"
    totalDelegatorsResult = execute_query(sqlQuery)

    labels1 = []
    data1 = []
    for reward in rewardsResult:
        labels1.append(str(reward['epoch_no']))
        data1.append(str(round(reward['amount']/MILLION,2)))

    labels1 = ','.join(labels1)
    data1 = ','.join(data1)

    labels2 = []
    data2 = []
    for totalStake in totalStakesResult:
        labels2.append(str(totalStake['epoch_no']))
        data2.append(str(round(totalStake['total_stake']/BILLION,2)))

    labels2 = ','.join(labels2)
    data2 = ','.join(data2)

    labels3 = []
    data3 = []

    for totalPools in totalPoolsResult:
        labels3.append(str(totalPools['epoch_no']))
        data3.append(str(totalPools['amount']))

    labels3 = ','.join(labels3)
    data3 = ','.join(data3)

    labels4 = []
    data4 = []
    for totalDelegators in totalDelegatorsResult:
        labels4.append(str(totalDelegators['epoch_no']))
        data4.append(str(totalDelegators['amount']))

    labels4 = ','.join(labels4)
    data4 = ','.join(data4)

    labels5 = []
    data5 = []
    for totalPledge in totalPledgeResult:
        labels5.append(str(totalPledge['epoch_no']))
        data5.append(str(round(totalPledge['total_pledge']/MILLION,2)))

    labels5 = ','.join(labels5)
    data5 = ','.join(data5)

    return render(request, 'cardanopools/epochstatistics.html', {
        'labels1': labels1,
        'labels2': labels2,
        'labels3': labels3,
        'labels4': labels4,
        'labels5': labels5,
        'data1': data1,
        'data2': data2,
        'data3': data3,
        'data4': data4,
        'data5': data5,
    })

# Top 100 richest address
def richestlist(request):

    # Get usd price from coingecko.com
    response = requests.get('https://api.coingecko.com/api/v3/coins/cardano')
    json_data = json.loads(response.text)
    price = json_data['market_data']['current_price']['usd']

    # Get top 100 richest address
    sqlQuery = "SELECT * FROM richest_address LIMIT 100;"
    richestAddressResult = execute_query(sqlQuery)

    richestAddress = []
    for address in richestAddressResult:
        temp = {}
        temp['address'] = address['address']
        temp['balance'] = f"{round(address['balance'],2):,}"
        temp['usdbalance'] = f"{round(address['balance'] * Decimal(price),2):,}"
        richestAddress.append(temp)

    return render(request, 'cardanopools/richestlist.html', {
        'richestAddress': richestAddress,
    })
