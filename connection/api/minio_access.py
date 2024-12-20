from minio import Minio
from minio.error import S3Error
import configparser
import time
from datetime import timedelta
import os
from urllib.parse import urlparse, urlunparse


client = None

def main():
    global client
    # Create a configparser object and read it
    config = configparser.ConfigParser(allow_no_value = True)
    # Update with right user (use case/ DYNABIC component)
    config.read('minio_config.ini')
    # Initialize client:
    client = Minio(config.get('minio', 'endpoint'),
        access_key=config.get('minio', 'access_key'),
        secret_key=config.get('minio', 'secret_key'),
        secure = config.getboolean('minio', 'secure'))


### Bucket Operations ###
def create_bucket(bucket_name):
    '''
        Create bucket with bucket_name name.
    '''
    global client
    try:
        main()
    except S3Error as exc:
        print("[minio_access.py] Error occurred.", exc)
    # Create 'bucket_name' bucket if it does not exist.
    found = client.bucket_exists(bucket_name)
    if not found:
        client.make_bucket(bucket_name)
        buckets = client.list_buckets()
        creation_date = next((bucket.creation_date for bucket in buckets if bucket_name == bucket.name), None)
        print(f"[minio_access.py] Bucket {bucket_name} has been created: {creation_date}.")
    else:
        print(f"[minio_access.py] Bucket {bucket_name} already exists.")
    # Tested

def list_buckets():
    '''
        List available buckets in database.
    '''
    global client
    try:
        main()
    except S3Error as exc:
        print("[minio_access.py] Error occurred.", exc)
    buckets = client.list_buckets()
    print(f"[minio_access.py] MinIO Database consists of following {len(buckets)} buckets:")
    for bucket in buckets:
        print(bucket.name)
    # Tested

def remove_bucket(bucket_name):
    '''
        Removes bucket with given name (empty or not).
    '''
    global client
    try:
        main()
    except S3Error as exc:
        print("[minio_access.py] Error occurred.", exc)
    try:
        objects = client.list_objects(bucket_name)
        object_list = list(objects)
        if len(object_list) != 0:
            # Delete each object in the bucket
            object_names = [obj.object_name for obj in object_list]
            for obj_name in object_names:
                remove_object(bucket_name, obj_name)
        # After all objects have been removed, delete the empty bucket
        client.remove_bucket(bucket_name)
        print(f"[minio_access.py] Bucket '{bucket_name}' has been deleted, along with its content.")
    except Exception as e:
        print(f"[minio_access.py] An error occurred: {str(e)}")
    # Tested

def list_objects(bucket_name, prefix = None, recursive = False):
    '''
        List objects from given bucket (and using eventual prefix).
    '''
    global client
    try:
        main()
    except S3Error as exc:
        print("[minio_access.py] Error occurred.", exc)
    found = client.bucket_exists(bucket_name)
    if not found:
        print(f"[minio_access.py] Bucket {bucket_name} does not exist.")
    else:
        objects = client.list_objects(bucket_name, prefix=prefix)
    return objects

#TODO: Other bucket operations: set/delete encryption
### Object Operations ###

def get_object(bucket_name, object_name, prefix = None, version_id=None):
    '''
        Get object data from given bucket (and using eventual prefix).
    '''
    global client
    try:
        main()
    except S3Error as exc:
        print("[minio_access.py] Error occurred.", exc)
    if prefix is not None:
        object_name = prefix + object_name
    # TODO: Provide the correct SSE-C key if encrypted object
    try:
        response = client.get_object(bucket_name, object_name, version_id = version_id)
    finally:
        response.close()
        response.release_conn()
    # TODO: handle the HTTPResponse (fetch data, response status)
    # Tested
    return response

def download_object(bucket_name, object_name, file_path, prefix = None, version_id=None):
    '''
        Download object data from given bucket (and eventual prefix) to given path.
    '''
    global client
    try:
        main()
    except S3Error as exc:
        print("[minio_access.py] Error occurred.", exc)
    if prefix is not None:
        object_name = prefix + object_name

    # Ensure the directory exists:
    directory = os.path.dirname(file_path)
    if not os.path.exists(directory):
        os.makedirs(directory)

    # TODO: Provide the correct SSE-C key if encrypted object
    client.fget_object(bucket_name, object_name, file_path, version_id = version_id)
    # Tested

def download_last_object(bucket_name, file_path, prefix = None, version_id=None):
    '''
        Download lastly modified/added object data from given bucket (and eventual prefix) to given path.
    '''
    global client
    try:
        main()
    except S3Error as exc:
        print("[minio_access.py] Error occurred.", exc)
    try:
        # List objects in the bucket
        objects = client.list_objects(bucket_name, prefix=prefix, recursive=True)
        # Retrieve the latest added object
        latest_object = max(objects, key=lambda obj: obj.last_modified)
        # Download object locally on path
        # Use the object's original name for the download path
        file_path = os.path.join(file_path, latest_object.object_name)
        # TODO: Provide the correct SSE-C key if encrypted object
        client.fget_object(bucket_name, latest_object.object_name, file_path, version_id = version_id)
        print("[minio_access.py] Local download complete.")
    except S3Error as exc:
        print("[minio_access.py] Error occurred:", exc)
   

def upload_object(bucket_name, object_name, file_path, prefix = None, metadata = None):
    '''
        Upload object (and eventual metadata) to given bucket (and using eventual prefix) from given path.
        Remmber to add the extension to object_name as well!
    '''
    global client
    try:
        main()
    except S3Error as exc:
        print("[minio_access.py] Error occurred.", exc)
    if prefix is not None:
        object_name = prefix + object_name
    # TODO: Upload with customer key/KMS/S3 type of server-side encryption.
    result = client.fput_object(bucket_name, object_name, file_path, metadata = metadata)
    print("[minio_access.py] Uploaded {0} object with version-id: {1} to {2} bucket. ".format(result.object_name, result.version_id, bucket_name),)
    # Tested

def remove_object(bucket_name, object_name, prefix = None, version_id=None):
    '''
        Upload object (and eventual metadata) to given bucket (and using eventual prefix) from given path.
    '''
    global client
    try:
        main()
    except S3Error as exc:
        print("[minio_access.py] Error occurred.", exc)
    if prefix is not None:
        object_name = prefix + object_name
    client.remove_object(bucket_name, object_name, version_id = version_id)
    print("[minio_access.py] Removed {0} object with version-id: {1} from {2} bucket. ".format(object_name, version_id, bucket_name),)
    # Tested

def print_info_object(bucket_name, object_name, prefix = None, version_id=None):
    '''
        Print object (and metadata) information given bucket location (using eventual prefix) and version.
    '''
    global client
    try:
        main()
    except S3Error as exc:
        print("[minio_access.py] Error occurred.", exc)
    if prefix is not None:
        object_name = prefix + object_name
    # TODO: Provide the correct SSE-C key if encrypted object
    result = client.stat_object(bucket_name, object_name, version_id = version_id)
    # TODO: Provide more info (depends on need)
    string_to_be_returned = "Object "+object_name+" was last-modified: "+str(result.last_modified)+", and has size: "+str(result.size)
    print("[minio_access.py] Object {0} was last-modified: {1}, has size: {2}".format(object_name, result.last_modified, result.size,),)
    # Tested
    return string_to_be_returned

def get_url_object(bucket_name, object_name, prefix = None, version_id=None, expires = timedelta(hours=1)):
    '''
        Obtain object (and metadata) download URL given bucket location (using eventual prefix) and version. Link expires afters a (default) 1 hour period.
    '''
    global client
    try:
        main()
    except S3Error as exc:
        print("[minio_access.py] Error occurred.", exc)
    if prefix is not None:
        object_name = prefix + object_name
    url = client.presigned_get_object(bucket_name, object_name, expires=expires)
    print("[minio_access.py] Object {0} - download URL (expires soon!): {1}".format(object_name, url,),)
    # Tested
    return url

def get_url_last_object(bucket_name, prefix=None, expires=timedelta(hours=1)):
    '''
    Obtain URL for the last added object (using optional prefix) in a bucket. Link expires after a (default) 1 hour period.
    '''
    global client
    try:
        main()
    except S3Error as exc:
        print("[minio_access.py] Error occurred.", exc)
    try:
        # List objects in the bucket
        objects = client.list_objects(bucket_name, prefix=prefix, recursive=True)
        # Retrieve the latest added object
        latest_object = max(objects, key=lambda obj: obj.last_modified)
        # Get the URL for the latest object
        url = client.presigned_get_object(bucket_name, latest_object.object_name, expires=expires)
        print("[minio_access.py] Last added object - download URL (expires soon!):", url)
        return url
    except S3Error as exc:
        print("[minio_access.py] Error occurred:", exc)
        return None
    
'''
if __name__ == "__main__":
    try:
        main()
    except S3Error as exc:
        print("error occurred.", exc)
'''
