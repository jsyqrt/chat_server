# Zchat 应用

## 部署文档

完整的生产环境部署和运维指南请查看 [生产环境部署与运维指南](doc/production_deployment_guide.md)

## 常用命令

# install ocr tool
sudo apt-get install tesseract-ocr
wget https://github.com/tesseract-ocr/tessdata/raw/refs/heads/main/chi_sim.traineddata
tesseract --list-langs
mv chi_sim.traineddata to path (like /usr/share/tesseract-ocr/5/tessdata/)

# init db, maybe not necessary
flask --app zchat init-db

# init roadmaps
cp zchat/roadmap/mindmaps/*_cn.json instance
curl -X SET 'http://localhost:5000/roadmap/reset_official_roadmaps'

# steps for db migrate
1. [only once] flask --app zchat migrate init
2. change models.py
3. flask --app zchat migrate migrate -m "changes I've made"
4. check migrate py file
5. flask --app zchat migrate upgrade

pybabel extract -F babel.cfg -k _l -o zchat/translations/messages.pot .
pybabel compile -d zchat/translations
pybabel update -i zchat/translations/messages.pot -d zchat/translations