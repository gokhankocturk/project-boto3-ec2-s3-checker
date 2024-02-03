'''
Required imports
    - boto3 for AWS
    - json for all JSON processing
    - datetime to get the current time
'''
import boto3
import json
from datetime import datetime

'''
Define the ec2 and s3 boto3 client which we can use as needed.
'''
ec2 = boto3.client('ec2')
s3 = boto3.client('s3')

'''
Define the tag-key values which will determine the instance needs to be stopped and/or started.
If instance doesnt have these tags, the scheduler will ignore the instance.
'''
label_start_time = "SchedulerStartTime"
label_stop_time = "SchedulerStopTime"

'''
Function to takes a spesific key as input and determine the associated value
if it exists in the instance tags.
'''

def get_instance_tag_value(key, tags):

    value = None
    for tag in tags:
        tag_key = tag['Key']
        if tag_key == key:
            value = tag['Value']
        if value is not None:
            break
    return value

'''
Return a list of all the instances that have the keys specified.
'''

def get_instance_with_tag(list_of_keys):

    instances = None

    response = ec2.describe_instances(
        Filters = [
            {
                "Name" : "tag-key",
                "Values" : list_of_keys
            }
        ]
    )

    if len(response['Reservations']) > 0:
        instances = response['Reservations'][0]['Instances']

    return instances

'''
Decide what to do with an instance, given the instance state and current hour:
    - if instance is running and stop_time is now, stop instance
    - if instance is stopped and start_time is now, start instance
    - in all other cases, leave the instance as is
'''

def process_instance(instance, current_hour):

    instance_id = instance['InstanceId']
    instance_state = instance['State']['Name']
    instance_tags = instance['Tags']

    print(f"Checking instance {instance_id}")

    do_nothing = True

    if instance_state == "running":
        stop_time_tag = get_instance_tag_value(label_stop_time, instance_tags)
        if stop_time_tag is not None and stop_time_tag.isdigit():
            if int(stop_time_tag) == current_hour:
                do_nothing = False
                result = f"Stopping instance {instance_id}"
                ec2.stop_instances(InstanceIds=[instance_id])

    if instance_state == "stopped":
        start_time_tag = get_instance_tag_value(label_start_time, instance_tags)
        if start_time_tag is not None and start_time_tag.isdigit():
            if int(start_time_tag) == current_hour:
                do_nothing = False
                result = f"Starting instance {instance_id}"
                ec2.start_instances(InstanceIds=[instance_id])

    if do_nothing:
        result = f"Instance {instance_id} is {instance_state}. Therefore no action required."

    return result

'''
Get the list of all instances that have the start and stop tags,
the process those instances.
'''

def process_instances():

    instances = get_instance_with_tag([label_start_time])

    if instances is None:
        return_status = "No instances found."
    else:
        print(f"Found {len(instances)} instances to process")
        now = datetime.now()
        current_hour = int(now.strftime("%H"))
        print(f"Current hour is {current_hour}")
        for instance in instances:
            message = process_instance(instance, current_hour)
            print(message)
            return_status = "Finished processing all instances."
    
    return return_status


def process_bucket(bucket_name):

    response = s3.get_bucket_versioning(Bucket=bucket_name)
    is_enabled = response.get("Status", "Disabled")

    if is_enabled == "Enabled":
        result = f"Versioning is enabled on {bucket_name}"
    else:
        versioning_configuration = {"Status" : "Enabled"}
        s3.put_bucket_versioning(Bucket=bucket_name, VersioningConfiguration=versioning_configuration)
        result = f"Enabling versioning on {bucket_name}"

    return result

def process_buckets():

    prefix = "aslan"

    response = s3.list_buckets()
    bucket_list = response['Buckets']
    if bucket_list == 0:
        return_status = "No buckets found."
    else:
        print(f"Found {len(bucket_list)} buckets to process")
        for bucket in bucket_list:
            bucket_name = bucket['Name']

            if bucket_name.startswith(prefix):
                message = process_bucket(bucket_name)
                print(message)
            else:
                message = f"Skipping the {bucket_name}"
                print(message)
        
        return_status = "Finished processing all buckets."
    
    return return_status


def lambda_handler(event, context):
    
    try:
        ec2_status = process_instances()
        s3_status = process_buckets()
        return_code = 200
        return_status = f"{ec2_status} {s3_status}"
    except Exception as e:
        return_code = 500
        return_status = f"Unexpected error has ocurred {e}"
    finally:
        print(return_status)
        return { "statusCode" : return_code, "body" : json.dumps(return_status)}


if __name__ == "__main__":
    lambda_handler(None, None)