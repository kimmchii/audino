import mysql.connector
from dataclasses import dataclass
from typing import NamedTuple, List, Tuple, Dict
from enum import Enum, auto 

class UserColumn(Enum):
  TABLE_NAME = "user"
  ID = "id"
  USERNAME = "username"
  ROLE_ID = "role_id"

class SegmentColumn(Enum):
  TABLE_NAME = "segmentation"
  ID = "id"
  DATA_ID = "data_id"
  TRANSCRIPTION = "transcription"

class DataColumn(Enum):
  TABLE_NAME = "data"
  ID = "id"
  PROJECT_ID = "project_id"
  ASSINGED_USER_ID = "assigned_user_id"
  IS_MARKED_FOR_REVIEW = "is_marked_for_review"

@dataclass
class ConnectorObject:
  host: str
  user: str
  password: str
  database: str
  port: int = 3306

@dataclass
class AudioObject:
  audio_id: int
  project_id: int
  assigned_user: str
  is_marked_for_review: bool
  is_empty_transcript: bool

def connect_mysql(connector_object: dataclass) -> mysql.connector.connection:
  """
  Connects to a mysql database by using host, user, password, and port and returns its connection.
  To get the host address, run the following command 
  `docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' <container ID>`.
  We can get the`container ID` by running `docker ps`, 
  in the case of the mysql in audino, it locates at the container name `audino-mysql-x`.
  """
  mysql_connection = mysql.connector.connect(
    host = connector_object.host,
    user = connector_object.user,
    password = connector_object.password,
    database = connector_object.database,
    port = connector_object.port,
  )

  return mysql_connection

def query_from_table(
      mysql_connection: mysql.connector.connection,
      table_name: Enum, 
      column_lists: List[Enum], 
      condition: str = ""
    ) -> List[Tuple[any]]:
    """
    Queries the table according to the input column name in the database in this case, 
    we have already use `audino`. 
    """
    column_lists = [column.value for column in column_lists]
    query = f"SELECT {','.join(column_lists)} FROM {table_name.value}"
    query += f" WHERE {condition}" if condition else ""

    cursor = mysql_connection.cursor(buffered=True)
    cursor.execute(query)
    queried_datas = cursor.fetchall()

    return queried_datas


def get_ids_and_username( 
    mysql_connection: mysql.connector.connection,
    table_name: str, 
    column_lists: List[str], 
  ) -> Dict[str, str]:
  """
  Returns the conversion dict for users in the database,
  the result conversion dict will be {id: username}.
  """
  ids_and_usernames = query_from_table(
    mysql_connection = mysql_connection, 
    table_name = table_name, 
    column_lists = column_lists,
  )
  id_user_conversion_dict = {}
  for id, username in ids_and_usernames:
      id_user_conversion_dict[str(id)] = username
  
  return id_user_conversion_dict

  
def get_transcripts_status(
    mysql_connection: mysql.connector.connection,
    table_name: Enum, 
    column_lists: List[Enum], 
  ) -> Dict[str, List[int | bool]]:
  """
  Returns the status of an annotated transcript. If the transcript is found but empty, set its status, 
  `is_empty_transcript` to True.
  """
  audio_ids = query_from_table(
      mysql_connection = mysql_connection, 
      table_name = table_name, 
      column_lists = column_lists,
    )
  
  id_transcript_dict = {"id":[], "is_empty_transcript":[]}
  for audio_id, transcription in audio_ids:
    id_transcript_dict["id"].append(audio_id)
    # Removes extra space and prevent the empty string to be recongnised as `already transcript`
    clean_data = transcription.strip()
    # Appends False if the audio's transcript is not empty.
    is_empty_text = len(clean_data) == 0
    id_transcript_dict["is_empty_transcript"].append(is_empty_text)

  return id_transcript_dict


def get_audios_attributes(
    mysql_connection: mysql.connector.connection,
    table_name: Enum, 
    column_lists: List[Enum], 
    id_transcript_dict: Dict[str, List[int | bool]],
  ) : # TODO define the return type 
  """
  Returns the audios's attribute which consists of audio_id, project_id, assigned_user, 
  is_marked_for_review, and is_empty_transcript.
  """
  audios_attributes = query_from_table(
    mysql_connection = mysql_connection,
    table_name = table_name,
    column_lists = column_lists,
  )

  audio_attributes_list = []
  for audio_id, project_id, assigned_user, is_mark_for_review in audios_attributes:
    audio_object = AudioObject(
      audio_id = audio_id,
      project_id = project_id,
      assigned_user = id_user_conversion_dict[str(assigned_user)],
      is_marked_for_review = bool(is_mark_for_review),
      is_empty_transcript = True,
    )
    audio_attributes_list.append(audio_object)

  for i, id_value in enumerate(id_transcript_dict["id"]):
    # Shifts an index b.c. sql starts with 1, chang the value from True to False if the audio contain a transcript.
    # BUG could happen at `id_value`, better safty is needed
    audio_attributes_list[id_value-1].is_empty_transcript = id_transcript_dict["is_empty_transcript"][i]

  return audio_attributes_list


def construct_attributes_by_user_dict(
    audio_attributes_list, # TODO Define the input type
  ) -> Dict[str, List[Dict[str, int | bool]]]:
  """
  Constructs the dictionary that has a key as "assigned_user" and a value as a list of its properties.
  the list contains "audio_id", "project_id", "is_marked_for_review", and "is_empty_transcript"
  """
  user_attributes_dict = {}
  for element in audio_attributes_list:
    # Create an empty list for key if the audio_attribute_list has no that assigned_user
    if element.assigned_user not in user_attributes_dict:
      user_attributes_dict[element.assigned_user] = []
    
    key = element.assigned_user
    # Get the dictionary representation of the DataObject
    element_dict = element.__dict__.copy()  
    # Remove the assigned_user attribute from the element
    del element_dict["assigned_user"]  
    user_attributes_dict[key].append(element_dict)

  return user_attributes_dict


def relocate_files_from_users(
    mysql_connection: mysql.connector.connection,
    user_attributes_dict: Dict[str, List[Dict[str, int | bool]]],
    from_username: List[str],
    target_username: str,
    table_name: Enum, 
    column_name: Enum, 
    id_user_conversion_dict: Dict[str, str]
  ) -> None:
  """"""
  # List the audio ids that we're going to relocate based on `from_user`.
  moved_audio_ids = []
  for user_id in from_username:
    for attributes in user_attributes_dict[user_id]:
        if not(attributes["is_marked_for_review"] and attributes["is_empty_transcript"]):
            moved_audio_ids.append(attributes["audio_id"])
  
  # Connect a cursor to mysql database.
  cursor = mysql_connection.cursor(buffered=True)
  
  # TODO Optimize to below part
  for id, username in id_user_conversion_dict.items():
      if username == target_username:
        for audio_id in moved_audio_ids:
            query = f"UPDATE {table_name} SET {column_name} = {id} WHERE id = {audio_id}"
            cursor.execute(query)
            mysql_connection.commit()


if __name__ == "__main__":
  connector_obj = ConnectorObject(
    host="172.18.0.2",
    user="audino",
    password="audino",
    database="audino",
    port=3306,
  )
  mysql_connection = connect_mysql(connector_obj)

  id_user_conversion_dict = get_ids_and_username(
                              mysql_connection = mysql_connection,
                              table_name = UserColumn.TABLE_NAME,
                              column_lists = [UserColumn.ID, UserColumn.USERNAME],
                            )
  
  transcript_status = get_transcripts_status(
                        mysql_connection = mysql_connection,
                        table_name = SegmentColumn.TABLE_NAME,
                        column_lists = [SegmentColumn.DATA_ID, SegmentColumn.TRANSCRIPTION],
                      )

  audio_attribute_list = get_audios_attributes(
                           mysql_connection = mysql_connection,
                           table_name = DataColumn.TABLE_NAME,
                           column_lists = [ DataColumn.ID, 
                                           DataColumn.PROJECT_ID, 
                                           DataColumn.ASSINGED_USER_ID, 
                                           DataColumn.IS_MARKED_FOR_REVIEW
                                          ],
                           id_transcript_dict = transcript_status
                         )
  user_attributes_dict = construct_attributes_by_user_dict(
                           audio_attributes_list = audio_attribute_list, 
                         )
  
  relocate_files_from_users(
    mysql_connection = mysql_connection,
    user_attributes_dict = user_attributes_dict,
    from_username = [],
    target_username = s, 
    table_name = DataColumn.TABLE_NAME,
    id_user_conversion_dict = id_user_conversion_dict,
  )
