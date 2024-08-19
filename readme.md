# init db
flask --app zchat init-db

# gen random data
curl -v -X GET "http://127.0.0.1:5000/user/gen_random?count=200"

# steps for db migrate
1. [only once] flask --app zchat migrate init
2. change models.py
3. flask --app zchat migrate migrate -m "changes I've made"
4. check migrate py file
5. flask --app zchat migrate upgrade
