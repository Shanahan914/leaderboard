from redis.exceptions import RedisError
import time



# generic function to retry an operation -> this will retry if there is a redis set failure
def retry_cache_operation(operation, *args, retries=3, delay=0.5, logger):
    for attempt in range(retries):
        try:
            operation(*args)
            return
        except RedisError as e:
            logger.error(f"Redis error (attempt {attempt + 1}/{retries}): {str(e)}")
            if attempt < retries - 1:
                time.sleep(delay * (2 ** attempt))
            else:
                raise e


