.PHONY: buildimages

buildimages:
	docker build -t rewolproxy -f Dockerfile.rewolproxy .
	docker build -t rewolserver -f Dockerfile.rewolserver .

cleanimages:
	docker rmi rewolproxy rewolserver
