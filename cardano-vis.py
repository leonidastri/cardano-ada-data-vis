import psycopg2
import time
import matplotlib.pyplot as plt
import numpy as np
import requests,json
import statistics
from decimal import *
from requests.exceptions import ConnectionError

# Database configuration values
db_config = {'database': "cexplorer",
             'user': "admin",
             'password': "admin",
             'host': "127.0.0.1",
             'port': "5432"}

# Connect to db 
def connect_to_db(db=db_config):
    try:
        con = psycopg2.connect( database=db['database'], 
                                user=db['user'], 
                                password=db['password'], 
                                host=db['host'], 
                                port=db['port'])
        print("Connected!")
        return con
    except:
        print ("I am unable to connect to the database.")
        return

#################################
# Methods to query connected db #
#################################

# execute query without params
def execute_query(con, sql_statement):
    cursor = con.cursor()
    cursor.execute(sql_statement)

# execute query without params and fetch result
def execute_query_result(con, sql_statement):
    cursor = con.cursor()
    cursor.execute(sql_statement)
    return dictfetchall(cursor)
    
# execute query with params and fetch result
def execute_query_params(con, sql_query, params):
    cursor = con.cursor()
    cursor.execute(sql_query,params)
    return dictfetchall(cursor)

# fetch results
def dictfetchall(cursor):
    "Return all rows from a cursor as a dict"
    columns = [col[0] for col in cursor.description]
    return [
        dict(zip(columns, row))
        for row in cursor.fetchall()
    ]

# Connect to db 
def connect_to_db(db=db_config):
    try:
        con = psycopg2.connect( database=db['database'], 
                                user=db['user'], 
                                password=db['password'], 
                                host=db['host'], 
                                port=db['port'])
        print("Connected!")
        return con
    except:
        print ("I am unable to connect to the database.")
        return

###########
# metrics #
###########

MILLION = 1000000
BILLION = 1000000000

# Create plot
def create_plot(data):

    plt.figure(figsize=(8,4))

    x_ticks = np.arange(data['x'][0], data['x'][-1]+1, 10)
    plt.xticks(x_ticks)

    plt.ylim([0,3/2*max(data['y'])])

    plt.plot(data['x'],data['y'])
    plt.title(data['title'])

    plt.xlabel(data['xlabel'])
    plt.ylabel(data['ylabel'])

    plt.grid(axis = 'y')
    plt.fill_between(data['x'], data['y'])

    plt.savefig('plots/' + data['file'])
    plt.clf()

# Create bar plot for 51% attacks
def create_bar_plot_51(data):

    plt.figure(figsize=(8,4))
    plt.title('Lowest Number of ' + data['entity'] + ' Owning In Total More Than 50% of Total Stake')

    if (data['entity'] != 'Addresses'):
        labels = ['Latest Snapshot', 'Current State']
    else:
        labels = ['Current State']

    plt.ylabel(data['entity'])
    plt.ylim([0,3/2*max(data['data'])])
    plt.bar(labels,data['data'], width = 0.8)

    plt.savefig('plots/' + data['file'])
    plt.clf()

# Create histogram
def create_hist(data):

    # width of histogram bars
    width = 20
    # max value of histogram
    max = 100

    plt.title('Leverages - Epoch ' + str(data['epoch']))

    plt.xlabel('Leverage')
    plt.ylabel('Total Count')
    
    plt.hist(data['data'], bins=range(0, max + width, width))

    plt.savefig('plots/' + data['file'])
    plt.clf()

# Compute rewards per epoch
def rewards_per_epoch(con):

    # Get total rewards per epoch (from new table "total_epoch_rewards" created)
    sqlQuery = "SELECT * FROM total_epoch_rewards;"
    rewardsResult = execute_query_result(con,sqlQuery)

    labels = []
    data = []
    for reward in rewardsResult:
        labels.append(int(reward['epoch_no']))
        data.append(float(round(reward['amount']/MILLION,2)))

    return {'x':labels,'y':data, 'xlabel': 'Epochs', 'ylabel': 'Rewards', 'title': "Rewards Per Epoch", 'file': 'rewards-per-epoch.png'}

# Compute total stake per epoch
def total_stake_per_epoch(con):

    # Get total stake per epoch (from new table "total_epoch_stake" created)
    sqlQuery = "SELECT * FROM total_epoch_stake;"
    totalStakesResult = execute_query_result(con,sqlQuery)

    labels = []
    data = []
    for totalStake in totalStakesResult:
        labels.append(int(totalStake['epoch_no']))
        data.append(float(round(totalStake['total_stake']/BILLION,2)))

    return {'x':labels,'y':data, 'xlabel': 'Epochs', 'ylabel': 'Total Stake', 'title': "Total Stake Per Epoch", 'file': 'total-stake-per-epoch.png'}

# Compute total pools per epoch
def total_pools_per_epoch(con):

    # Get total pools per epoch (from new table "total_epoch_pools" created)
    sqlQuery = "SELECT * FROM total_epoch_pools;"
    totalPoolsResult = execute_query_result(con,sqlQuery)

    labels = []
    data = []
    for totalPools in totalPoolsResult:
        labels.append(int(totalPools['epoch_no']))
        data.append(int(totalPools['amount']))
    
    return {'x':labels,'y':data, 'xlabel': 'Epochs', 'ylabel': 'Pools amount', 'title': "Pools Per Epoch", 'file': 'pools-per-epoch.png'}

# Compute total delegators per epoch
def total_delegators_per_epoch(con):

    # Get total delegators per epoch
    sqlQuery = "select count(*) as amount, epoch_no from epoch_stake group by epoch_no ORDER BY epoch_no ASC;"
    totalDelegatorsResult = execute_query_result(con,sqlQuery)

    labels = []
    data = []
    for totalDelegators in totalDelegatorsResult:
        labels.append(int(totalDelegators['epoch_no']))
        data.append(int(totalDelegators['amount']))

    return {'x':labels, 'y': data, 'xlabel': 'Epochs', 'ylabel': 'Delegators', 'title': "Delegators Per Epoch", 'file': 'delegators-per-epoch.png'}

# Compute median leverage, 25th percentile leverage and 75th percentile leverage per epoch
def leverage_per_epoch(con,option):

    # Query to find minimum and maximum epoch
    sqlQuery = "SELECT MIN(epoch_no) as min_epoch, MAX(epoch_no) max_epoch FROM epoch_stake;"
    result = execute_query_result(con,sqlQuery)
    min_epoch = result[0]['min_epoch']
    max_epoch = result[0]['max_epoch']

    labels = []
    data = []

    # For each epoch from minimum to maximum epoch
    for epoch in range(min_epoch,max_epoch+1):
        params = [epoch, epoch, epoch, epoch]
        # Find every leverage [leverage of single pools and leverage of groups of pools]
        sqlQuery = "(SELECT leverage,epoch_no FROM epoch_leverage_no_group WHERE epoch_no = %s) UNION ALL (select leverage, epoch_no from epoch_leverage_group_3 where epoch_no = %s) UNION ALL (select leverage, epoch_no from epoch_leverage_group_4 where epoch_no = %s) UNION ALL (select leverage, epoch_no from epoch_leverage_group_5 where epoch_no = %s) ORDER BY leverage ASC;"
        epochLeverage = execute_query_params(con,sqlQuery,params)

        leverages = []
        for leverage in epochLeverage:
            leverages.append(float(round(leverage['leverage'],2)))

        # If option is equal to 1 compute median leverage
        if option==1:
            ylabel = 'Median Leverage'
            title = 'Median Leverage per Epoch'
            fname = 'median-leverage.png'
            data.append((statistics.median(leverages)))
        # If option is equal to 2 compute 25th percentile leverage
        elif option==2:
            ylabel = '25th Percentile Leverage'
            title = '25th Percentile Leverage per Epoch'
            fname = '25th-percentile-leverage.png'
            data.append((np.percentile(leverages, 25, interpolation = 'midpoint')))
        # If option is equal to 3 compute 75th percentile leverage
        else:
            ylabel = '75th Percentile Leverage'
            title = '75th Percentile Leverage per Epoch'
            fname = '75th-percentile-leverage.png'
            data.append((np.percentile(leverages, 75, interpolation = 'midpoint')))
        
        xlabel = 'Epochs'
        labels.append(int(leverage['epoch_no']))


    return {'x':labels, 'y':data, 'xlabel': xlabel, 'ylabel': ylabel, 'title': title, 'file': fname}

# Compute over-saturated pools per epoch [from epoch 234 where k parameter changed]
def oversaturated_pools(con):
    sqlQuery = "select count(*), epoch_no from epoch_pool_stake where stake > 64000000 and epoch_no >= 234 group by epoch_no order by epoch_no;"
    overSaturatedPoolsCountResult = execute_query_result(con,sqlQuery)

    labels = []
    data = []
    for overSaturatedPoolsCount in overSaturatedPoolsCountResult:
        labels.append(int(overSaturatedPoolsCount['epoch_no']))
        data.append(int(overSaturatedPoolsCount['count']))

    return {'x':labels, 'y':data, 'xlabel': 'Epochs', 'ylabel': 'Pools amount', 'title': "Over-saturated Pools", 'file': 'over-saturated-pools.png'}

# Compute ratio between total pools in groups and total pools in the system [per epoch]
def ratio_pools_in_groups_total_pools(con,min_epoch):
    
    # Find latest epoch from 
    sqlQuery = "select max(epoch_no) from epoch_stake;"
    max_epoch = int(execute_query_result(con,sqlQuery)[0]['max'])

    labels = []
    poolsInGroupsPerEpoch = []
    # For each epoch from minimum to maximum epoch
    for epoch in range(min_epoch,max_epoch+1):
        labels.append(epoch)
        params = [epoch]
        poolsSum = 0

        # Get groups of ticker prefix of 3 chracters length
        sqlQuery = "select count(*) from group_3_ids where epoch_no = %s group by epoch_no;"
        group3PoolsCountResult = execute_query_params(con,sqlQuery,params)

        # For every group with ticker prefix of 3 characters length, get number of pools and add them in poolsSum
        for group3 in group3PoolsCountResult:
            poolsSum += group3['count']

        # Get groups of ticker prefix of 4 chracters length
        sqlQuery = "select count(*) from group_4_ids where epoch_no = %s group by epoch_no;"
        group4PoolsCountResult = execute_query_params(con,sqlQuery,params)

        # For every group with ticker prefix of 4 characters length, get number of pools and add them in poolsSum
        for group4 in group4PoolsCountResult:
            poolsSum += group4['count']

        # Get groups of ticker prefix of 5 chracters length
        sqlQuery = "select count(*) from group_5_ids where epoch_no = %s group by epoch_no;"
        group5PoolsCountResult = execute_query_params(con,sqlQuery,params)

        # For every group with ticker prefix of 5 characters length, get number of pools and add them in poolsSum
        for group5 in group5PoolsCountResult:
            poolsSum += group5['count']

        poolsInGroupsPerEpoch.append(poolsSum)

    # Find total pools per epoch
    sqlQuery = "select * from total_epoch_pools order by epoch_no;"
    poolsPerEpochResult = execute_query_params(con,sqlQuery,params)

    poolsPerEpoch = []
    for total_pools in poolsPerEpochResult:
        poolsPerEpoch.append(total_pools['amount'])
    
    # Compute ratio between total pools in groups and total pools per epoch
    data = [float(a/b) for a,b in zip(poolsInGroupsPerEpoch,poolsPerEpoch)]

    return {'x':labels, 'y':data, 'xlabel': 'Epochs', 'ylabel': 'Ratio', 'title': "Ratio Between Total Pools in Groups and Total Pools", 'file': 'ratio--pools-in-groups-total-pools.png'}

# Compute how many pools have more than 50% of current total supply [epoch stake from latest snapshot and live stake]
def attack_51_pools(con):
    
    data = []
    
    # Get total Supply
    sqlQuery = "SELECT current_supply FROM current_supply;"
    totalSupply = execute_query_result(con,sqlQuery)[0]['current_supply']

    # Get max epoch
    sqlQuery = "SELECT max(epoch_no) as max_epoch FROM epoch_stake;"
    maxEpoch = execute_query_result(con,sqlQuery)[0]['max_epoch']

    params = [maxEpoch]
    
    # Get total stake of each pool [epoch stake from latest snapshot]
    sqlQuery = "SELECT SUM(amount)/1000000 AS amount FROM epoch_stake WHERE epoch_no =  %s GROUP BY pool_id ORDER BY amount DESC"
    stakePerPool = execute_query_params(con,sqlQuery,params)

    poolCount = 0
    running_stake = 0
    # Compute how many addresses have more than 50% of current total supply [epoch stake from latest snapshot]
    for poolStake in stakePerPool:
        poolCount += 1
        running_stake += poolStake['amount']
        if running_stake >= Decimal(0.51) * totalSupply:
            break

    data.append(int(poolCount))

    # Get total stake of each pool [live_stake]
    sqlQuery = "SELECT sum(stake) as stake FROM live_stake GROUP BY pool_id ORDER BY stake DESC"
    stakePerPool = execute_query_params(con,sqlQuery,params)

    poolCount = 0
    running_stake = 0
    # Compute how many pools have more than 50% of current total supply [live stake]
    for poolStake in stakePerPool:
        poolCount += 1
        running_stake += poolStake['stake']
        if running_stake >= Decimal(0.51) * totalSupply:
            break

    data.append(int(poolCount))
    
    return {'data':data, 'entity': 'Pools', 'epoch': maxEpoch, 'file': '51-attack-pools.png'}

# Compute how many stake addresses have more than 50% of current total supply [epoch stake from latest snapshot and live stake]
def attack_51_stake_address(con):

    data = []
    
    # Get total Supply
    sqlQuery = "SELECT current_supply FROM current_supply;"
    totalSupply = execute_query_result(con,sqlQuery)[0]['current_supply']

    # Get max epoch
    sqlQuery = "SELECT max(epoch_no) as max_epoch FROM epoch_stake;"
    maxEpoch = execute_query_result(con,sqlQuery)[0]['max_epoch']

    params = [maxEpoch]

    # Get total stake of each stake address [epoch stake from latest snapshot]
    sqlQuery = "SELECT amount/1000000 AS amount FROM epoch_stake WHERE epoch_no = %s ORDER BY amount DESC"
    stakePerWallet = execute_query_params(con,sqlQuery,params)

    stakeAddressCount = 0
    running_stake = 0
    # Compute how many stake addresses have more than 50% of current total supply [epoch stake from latest snapshot]
    for walletStake in stakePerWallet:
        stakeAddressCount += 1
        running_stake += walletStake['amount']
        if running_stake >= Decimal(0.51) * totalSupply:
            break

    data.append(int(stakeAddressCount))

    # Get total stake of each stake address [live_stake]
    sqlQuery = "SELECT stake FROM live_stake ORDER BY stake DESC"
    stakePerWallet = execute_query_result(con,sqlQuery)

    stakeAddressCount = 0
    running_stake = 0
    # Compute how many stake addresses have more than 50% of current total supply [live stake]
    for walletStake in stakePerWallet:
        stakeAddressCount += 1
        running_stake += walletStake['stake']
        if running_stake >= Decimal(0.51) * totalSupply:
            break

    data.append(int(stakeAddressCount))

    return {'data':data, 'entity': 'Stake Addresses', 'epoch': maxEpoch, 'file': '51-attack-stake-addresses.png'}

# Compute how many addresses have more than 50% of current total supply
def attack_51_addresses(con):
    data = []

    # Get total Supply
    sqlQuery = "SELECT current_supply FROM current_supply;"
    totalSupply = execute_query_result(con,sqlQuery)[0]['current_supply']

    # Get max epoch
    sqlQuery = "SELECT max(epoch_no) as max_epoch FROM epoch_stake;"
    maxEpoch = execute_query_result(con,sqlQuery)[0]['max_epoch']

    params = [maxEpoch]

    # Get total balance of each address (UTxOs)
    sqlQuery = "SELECT balance FROM richest_address ORDER BY balance DESC"
    addressBalance = execute_query_result(con,sqlQuery)

    addressCount = 0
    running_stake = 0
    # Find how many addresses have more than 50% of current total supply
    for address in addressBalance:
        addressCount += 1
        running_stake += address['balance']
        if running_stake >= Decimal(0.51) * totalSupply:
            break

    data.append(int(addressCount))

    return {'data':data, 'entity': 'Addresses', 'epoch': maxEpoch, 'file': '51-attack-addresses.png'}

# Compute epoch leverages for specific input epoch
def epoch_leverages(con,epoch):
    
    params = [epoch, epoch, epoch, epoch]
    # Get leverage single pools and groups of pools
    sqlQuery = "(SELECT leverage,epoch_no FROM epoch_leverage_no_group WHERE epoch_no = %s) UNION ALL (select leverage, epoch_no from epoch_leverage_group_3 where epoch_no = %s) UNION ALL (select leverage, epoch_no from epoch_leverage_group_4 where epoch_no = %s) UNION ALL (select leverage, epoch_no from epoch_leverage_group_5 where epoch_no = %s) ORDER BY leverage ASC;"
    epochLeverage = execute_query_params(con,sqlQuery,params)

    leverages = []
    for leverage in epochLeverage:
        leverages.append(float(round(leverage['leverage'],2)))

    return {'data':leverages, 'epoch': epoch, 'file': 'hist-epoch-' + str(epoch) + '-leverage.png'}

def main():
    
    # Connect to database
    con = connect_to_db(db_config)

    # create plots

    # Create plot for total rewards per epoch
    data = rewards_per_epoch(con)
    create_plot(data)
    # Create plot for total stake per epoch
    data = total_stake_per_epoch(con)
    create_plot(data)
    # Create plot for total pools per epoch
    data = total_pools_per_epoch(con)
    create_plot(data)
    # Create plot for total delegators per epoch
    data = total_delegators_per_epoch(con)
    create_plot(data)

    # Create plot for median leverage per epoch
    data = leverage_per_epoch(con,option=1)
    create_plot(data)
    # Create plot for 25th percentile leverage per epoch
    data = leverage_per_epoch(con,option=2)
    create_plot(data)
    # Create plot for 75th percentile leverage per epoch
    data = leverage_per_epoch(con,option=3)
    create_plot(data)

    # Create plot for over-saturated pools per epoch [from epoch 234]
    data = oversaturated_pools(con)
    create_plot(data)
    # Create plot for ratio between total pools in groups and total groups per epoch
    data = ratio_pools_in_groups_total_pools(con,min_epoch=210)
    create_plot(data)

    # Create bar plots

    # Create bar plot for pools [51% Attack]
    data = attack_51_pools(con)
    create_bar_plot_51(data)
    # Create bar plot for stake addresses [51% Attack]
    data = attack_51_stake_address(con)
    create_bar_plot_51(data)
    # Create bar plot for addresses [51% Attack]
    data = attack_51_addresses(con)
    create_bar_plot_51(data)

    # Create histograms

    # Create histogram for leverages in epoch 235
    data = epoch_leverages(con,235)
    create_hist(data)
    # Create histogram for leverages in epoch 245
    data = epoch_leverages(con,245)
    create_hist(data)

    
    return 0 
    

if __name__ == "__main__":
    main()
