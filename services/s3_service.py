import boto3
import os
from django.conf import settings
from botocore.exceptions import ClientError, NoCredentialsError
import logging

logger = logging.getLogger(__name__)


class S3Service:
    """
    Service class for handling AWS S3 operations including file upload, 
    deletion, URL generation, and backup functionality.
    """
    
    def __init__(self):
        """
        Initialize S3 client with AWS credentials from Django settings.
        """
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=getattr(settings, 'AWS_REGION', 'us-east-1')
            )
            self.bucket_name = getattr(settings, 'AWS_S3_BUCKET', 'jfm02')
            
            # Test connection on initialization
            self._test_connection()
            
        except NoCredentialsError:
            logger.error("AWS credentials not found")
            raise Exception("AWS credentials not configured properly")
    
    def _test_connection(self):
        """
        Test S3 connection and bucket access
        """
        try:
            # Try to check if bucket exists and is accessible
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"Successfully connected to S3 bucket: {self.bucket_name}")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                logger.warning(f"Bucket {self.bucket_name} does not exist")
            elif error_code == '403':
                logger.warning(f"Access denied to bucket {self.bucket_name} - check permissions")
            else:
                logger.warning(f"Error accessing bucket {self.bucket_name}: {e}")
        except Exception as e:
            logger.warning(f"Could not test S3 connection: {e}")
    
    def upload_file(self, file, key):
        """
        Upload a file to S3 bucket.
        
        Args:
            file: File object to upload (BytesIO or similar)
            key (str): S3 object key (path/filename)
            
        Returns:
            bool: True if upload successful, False otherwise
        """
        try:
            # Ensure file is at the beginning
            file.seek(0)
            
            logger.info(f"Uploading {key} to bucket {self.bucket_name}")
            
            # Simple upload without ACL first
            self.s3_client.upload_fileobj(
                file,
                self.bucket_name,
                key,
                ExtraArgs={
                    'ContentType': self._get_content_type(getattr(file, 'name', key))
                }
            )
            
            logger.info(f"Successfully uploaded {key}")
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"S3 ClientError: {error_code} - {e.response['Error']['Message']}")
            return False
            
        except Exception as e:
            logger.error(f"Unexpected error uploading {key}: {e}")
            return False
    
    def delete_file(self, key):
        """
        Delete a file from S3 bucket.
        
        Args:
            key (str): S3 object key to delete
            
        Returns:
            bool: True if deletion successful, False otherwise
        """
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=key
            )
            logger.info(f"Successfully deleted {key} from {self.bucket_name}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to delete {key}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting {key}: {e}")
            return False
    
    def get_file_url(self, key):
        """
        Generate public URL for a file in S3 bucket.
        
        Args:
            key (str): S3 object key
            
        Returns:
            str: Public URL for the file
        """
        return f"https://{self.bucket_name}.s3.amazonaws.com/{key}"
    
    def copy_all_files(self, source_bucket, target_bucket):
        """
        Copy all files from source bucket to target bucket for backup purposes.
        
        Args:
            source_bucket (str): Source S3 bucket name
            target_bucket (str): Target S3 bucket name
            
        Returns:
            dict: Results with success count, failed files, and total processed
        """
        results = {
            'success_count': 0,
            'failed_files': [],
            'total_processed': 0
        }
        
        try:
            # List all objects in source bucket
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=source_bucket)
            
            for page in pages:
                if 'Contents' not in page:
                    continue
                    
                for obj in page['Contents']:
                    key = obj['Key']
                    results['total_processed'] += 1
                    
                    try:
                        # Copy object from source to target bucket
                        copy_source = {
                            'Bucket': source_bucket,
                            'Key': key
                        }
                        
                        self.s3_client.copy_object(
                            CopySource=copy_source,
                            Bucket=target_bucket,
                            Key=key,
                            ACL='public-read'
                        )
                        
                        results['success_count'] += 1
                        logger.info(f"Successfully copied {key} from {source_bucket} to {target_bucket}")
                        
                    except ClientError as e:
                        error_msg = f"Failed to copy {key}: {e}"
                        logger.error(error_msg)
                        results['failed_files'].append({
                            'key': key,
                            'error': str(e)
                        })
                        
            logger.info(f"Backup completed: {results['success_count']}/{results['total_processed']} files copied")
            return results
            
        except ClientError as e:
            logger.error(f"Failed to list objects in source bucket {source_bucket}: {e}")
            raise Exception(f"Cannot access source bucket: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during backup: {e}")
            raise Exception(f"Backup failed: {e}")
    
    def _get_content_type(self, filename):
        """
        Determine content type based on file extension.
        
        Args:
            filename (str): Name of the file
            
        Returns:
            str: MIME content type
        """
        extension = filename.lower().split('.')[-1] if '.' in filename else ''
        
        content_types = {
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'webp': 'image/webp',
            'bmp': 'image/bmp'
        }
        
        return content_types.get(extension, 'application/octet-stream')
    
    def file_exists(self, key):
        """
        Check if a file exists in the S3 bucket.
        
        Args:
            key (str): S3 object key to check
            
        Returns:
            bool: True if file exists, False otherwise
        """
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError:
            return False