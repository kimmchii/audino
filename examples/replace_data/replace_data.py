import mysql.connector

mydb = mysql.connector.connect(
  user="audino",
  password="audino",
  host='localhost', 
  port=3000,
)

print(mydb)