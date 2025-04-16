import boto3
import logging
import re
import random
import os

from botocore.exceptions import ClientError
from app.config import settings

logger = logging.getLogger(__name__)

def _load_cover_image_list():
    s3 = boto3.client(
        's3',
        region_name=settings.aws_region
    )

    try:
        response = s3.list_objects_v2(Bucket=settings.aws_bucket_name)
        allowed_extensions = {'.png', '.jpg', '.jpeg', '.gif'}
        
        # Filter and validate objects
        valid_images = []
        for obj in response['Contents']:
            key = obj['Key']
            # Skip directories (end with '/')
            if key.endswith('/'):
                continue
            # Check if it's an image file
            if any(key.lower().endswith(ext) for ext in allowed_extensions):
                valid_images.append(key)
        
        return valid_images
    except ClientError as e:
        logger.error(f"Error retrieving cover images from S3: {e}")
        return []

def load_cover_images():
    """
    Loads cover images from S3 and organizes them by archetype/keyword.
    """
    image_files = _load_cover_image_list()
    # Organize images by archetype/keyword
    cover_images = {}

    for image_file in image_files:
        # Extract base name (without extension or number)
        match = re.match(r'([a-zA-Z-]+)(\d+)\.\w+', image_file)
        if match:
            base_name = match.group(1)
            number = int(match.group(2))

            if base_name not in cover_images:
                cover_images[base_name] = []

            # Save full image path
            cover_images[base_name].append((number, image_file))

    # Sort each list by number
    for base_name in cover_images:
        cover_images[base_name].sort(key=lambda x: x[0])

    return cover_images

def select_cover_image(cover_images, term, random_image=True):
    """Select a cover image based on an archetype or keyword."""
    # If exact term doesn't exist, look for alternatives
    if term not in cover_images:
        # Look for similar terms (e.g., "hiking" might not exist, but "outdoors" does)
        similar_terms = [t for t in cover_images.keys() if t in term or term in t]

        if similar_terms:
            term = similar_terms[0]
        else:
            # If no similar terms, use a default category
            fallback_terms = ["lifestyle", "urban", "outdoors", "nature-lover", "cultural-explorer"]
            existing_terms = [t for t in fallback_terms if t in cover_images]

            if not existing_terms:
                # If none of the alternatives exist, return None
                return None

            term = random.choice(existing_terms)

    # If there are no images for this term, return None
    if not cover_images[term]:
        return None

    # Select a random image or the first one
    if random_image and len(cover_images[term]) > 1:
        image_idx = random.randint(0, len(cover_images[term]) - 1)
    else:
        image_idx = 0

    # Return the image path
    return cover_images[term][image_idx][1]

def get_s3_image_url(image_name: str, expiration: int = 3600) -> str:
    """
    Generate a signed S3 URL for an image that expires after the specified time.
    
    Args:
        image_name: The name/key of the image in S3
        expiration: Time in seconds for the URL to remain valid (default: 1 hour)
        
    Returns:
        A signed HTTPS URL for the image that expires after the specified time
    """
    s3 = boto3.client(
        's3',
        region_name=settings.aws_region
    )
    
    try:
        url = s3.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': settings.aws_bucket_name,
                'Key': image_name
            },
            ExpiresIn=expiration
        )
        return url
    except ClientError as e:
        logger.error(f"Error generating signed URL for image {image_name}: {e}")
        raise

