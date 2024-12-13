from api.database import SessionDep
import logging
from typing import List 
from sqlmodel import select
from api.models import User


## 0.1 logger ##

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s",
                    handlers=[
        logging.StreamHandler(),  # Logs to console
        logging.FileHandler("postgres.log")  # Logs to file
    ])

logger = logging.getLogger(__name__)


## 0.1 lookup various users from postgres
def retrieve_multiple_usernames_pg(list_of_ids : List[str], session):
    # get data from postgres
    try:
        data = session.exec(select(User).where(User.id.in_(list_of_ids))).all()
    except Exception as e:
        logger.error(f"Failure to read data from db: {e} for users: {list_of_ids}")
        return None
    
    if data is None:
        logger.error('Failed to retrieve data from db')
        return None
    
    # NOTE - need to add this 
    # # prepare data for writing
    # id_username_data = []
    # for item in data:
    #     id = getattr(item, 'id', None)
    #     username = getattr(item, 'username', None)
    #     id_username_data.append((id, username))
        
    return data


# take list of leaders [ids] and return dict with {rank : {username: (username), country: (country), date joined : (date)} 
def get_player_info(leaders : List[str], session : SessionDep):
    
    # get the postgres data
    leaders_data = retrieve_multiple_usernames_pg(leaders, session)

    # return if no data
    if leaders_data == None:
        return None
    
    # prepare leaders_data
    data_to_include= {'username', 'country', 'date_added'}

    cleaned_leaders_data = {str(leader.id) : {key: getattr(leader, key) for key in data_to_include} for leader in leaders_data}
    print(leaders)
    print('clean data', cleaned_leaders_data)

    # add ranks and map data to the correct position as in the ordered redis list
    ordered_leaders_data =  [
    {"rank": f"Player #{i + 1}", **cleaned_leaders_data[str(user_id)]}
    for i, user_id in enumerate(leaders)
    ]

    return ordered_leaders_data


