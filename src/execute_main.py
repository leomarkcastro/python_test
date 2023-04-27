import requests


def part1_upload():
    # Upload the file to the server
    url = 'http://127.0.0.1:8080/part1_upload'
    files = {
        'hierarchy': open('input/hierarchy.csv', 'rb'),
        'application': open('input/application.csv', 'rb'),
        'requests': open('input/requests.csv', 'rb'),
    }
    requests.post(url, files=files)


def part2_fetch():
    url = "http://127.0.0.1:8080/part2_fetch"
    requests.get(url, params={
        "corporateKey": "TT16TL"
    })
    requests.get(url, params={
        "corporateKey": "YS26IL"
    })
    requests.get(url, params={
        "corporateKey": "TF67FN"
    })


def part3_checkdb():
    url = "http://127.0.0.1:8080/part3_check"
    r = requests.get(url)
    print(r.text)


def main():
    part3_checkdb()
    part1_upload()
    part3_checkdb()
    part2_fetch()


if __name__ == '__main__':
    main()
