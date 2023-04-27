import cherrypy
import csv
import asyncio
from prisma import Prisma
import os


class MainServer(object):

    prisma = Prisma()

    # =============== Utilities

    def csv_parse(self, fileBuffer, delimiter=","):
        # We create a bytes buffer to store the file in memory
        textFileBuffer = bytes()

        # We read the file in chunks of 8192 bytes
        while True:
            data = fileBuffer.file.read(8192)
            # if there is no data left to read we break the loop
            if not data:
                break
            textFileBuffer += data

        # We decode the bytes buffer into a string
        textFileParse = textFileBuffer.decode("utf-8").splitlines()

        # print(textFileParse)

        # We create a csv reader object
        csv_reader = list(csv.reader(textFileParse, delimiter=delimiter))

        head_row = csv_reader[0]

        entries = []

        for row in csv_reader[1:]:
            entry = {}
            for key, value in zip(head_row, row):
                entry[key] = value
            entries.append(entry)

        return entries

    # =============== DB Connection

    async def connect(self):
        if self.prisma.is_connected() is False:
            await self.prisma.connect()

    async def disconnect(self):
        if self.prisma.is_connected():
            await self.prisma.disconnect()

    # =============== Part 1: Upload Funciton and Parsing

    async def hierarchy_upload(self, fileBuffer):
        data = self.csv_parse(fileBuffer)

        print(f"Received {len(data)} entries")

        for entry in data:

            # ======== we create the manager of the account, which is also an account
            manager = await self.prisma.user.find_unique(where={
                "uid": entry["managers_id"]
            })

            if manager is None:
                manager = await self.prisma.user.create({
                    "uid": entry["managers_id"],
                    "name": entry["managers"],

                })

            # ======== then, we create the actual account from the entry

            # check if account exists
            account = await self.prisma.user.find_unique(where={
                "uid": entry["uid"]
            })
            if account is None:
                # create account
                await self.prisma.user.create({
                    "uid": entry["uid"],
                    "name": entry["cn"],
                    "Manager": {
                        "connect": {
                            "uid": entry["managers_id"]
                        }
                    }
                })

    async def application_server_upload(self, fileBuffer):
        data = self.csv_parse(fileBuffer, ";")

        print(f"Received {len(data)} entries")

        for entry in data:

            # ======== we create the application and link it to their appropriate it custodian
            app_entry = await self.prisma.application.find_unique(where={
                "id": entry["app_id"]
            })

            if app_entry is None:
                itCustodian = await self.prisma.user.find_first(where={
                    "name": entry["itcustodian_name"]
                })

                itCustodianKey = await self.prisma.corporatekey.find_first(where={
                    "id": entry["it_custodian_ck"]
                })

                if (itCustodianKey is None):
                    itCustodianKey = await self.prisma.corporatekey.create({
                        "id": entry["it_custodian_ck"],
                        "User": {
                            "connect": {
                                "uid": itCustodian.uid
                            }
                        }
                    })
                await self.prisma.application.create({
                    "id": entry["app_id"],
                    "appName": entry["app_name"],
                    "itCustodian": {
                        "connect": {
                            "uid": itCustodian.uid
                        }
                    }
                })

            # ======== we create the server and link it to their appropriate it to the app

            server_entry = await self.prisma.server.find_unique(where={
                "id": entry["server_name"]
            })

            if server_entry is None:
                await self.prisma.server.create(data={
                    "id": entry["server_name"],
                    "environment": entry["environment"],
                    "Application": {
                        "connect": {
                            "id": entry["app_id"]
                        }
                    }
                })

    async def requests_upload(self, fileBuffer):
        data = self.csv_parse(fileBuffer, ";")

        print(f"Received {len(data)} entries")

        for entry in data:

            # ======== we create the requests here
            requests_entry = await self.prisma.requests.find_unique(where={
                "id": entry["User"]
            })

            if requests_entry is None:
                await self.prisma.requests.create({
                    "id": entry["User"],
                    "user": entry["User"],
                    "safe": entry["Safe"],
                    "action": entry["Action"],
                    "requestID": entry["Request ID"],
                    "reason": entry["Reason"],
                    "requestNumber": entry["Request Number"],
                    "Server": {
                        "connect": {
                            "id": entry["Target (server)"]
                        }
                    }
                })

    async def part1_upload_routine(self, hierarchy, application, requests):
        # print("Connecting to database")
        await self.connect()
        # print("Uploading hierarchy")
        await self.hierarchy_upload(hierarchy)
        # print("Uploading application and servers")
        await self.application_server_upload(application)
        # print("Uploading hierarchy")
        await self.requests_upload(requests)
        # print("Uploading hierarchy")
        await self.disconnect()

    @cherrypy.expose
    def part1_upload(self, hierarchy, application, requests):
        asyncio.run(self.part1_upload_routine(
            hierarchy, application, requests))

    async def fetch_records(self, corporateKey):

        # Get the owner of the corporate key
        user = await self.prisma.corporatekey.find_unique(where={
            "id": corporateKey
        }, include={
            "User": True
        })

        queue_to_check_server = set()
        queue_to_check_recursively = set()

        queue_to_check_server.add(user.User.uid)
        queue_to_check_recursively.add(user.User.uid)

        # Get all of the subordinates (of the subordinates, probably recursively) of the owner
        while len(queue_to_check_recursively) > 0:
            uid = queue_to_check_recursively.pop()
            subordinates = await self.prisma.user.find_many(where={
                "Manager": {
                    "uid": uid
                }
            }, include={
                "Manager": True
            })
            for subordinate in subordinates:
                queue_to_check_server.add(subordinate.uid)
                queue_to_check_recursively.add(subordinate.uid)

        # Get all of the requests that the subordinates have access to
        requests = await self.prisma.requests.find_many(where={
            "Server": {
                "Application": {
                    "itCustodian": {
                        "uid": {
                            "in": list(queue_to_check_server)
                        }
                    }
                }
            }
        }, include={
            "Server": True
        })

        # Create a csv file of the requests and export it into the output folder
        requests_csv = "User;Safe;Action;Request ID;Reason;Request Number;Target (server)\n"
        for request in requests:
            requests_csv += f"{request.user};{request.safe};{request.action};{request.requestID};{request.reason};{request.requestNumber};{request.Server.id}\n"

        # if output folder does not exist, create it
        if not os.path.exists("output"):
            os.makedirs("output")

        with open(f"output/request_key[{corporateKey}].csv", "w") as f:
            f.write(requests_csv)

    async def part2_fetch_routine(self, corporateKey):
        # print("Connecting to database")
        await self.connect()
        # print("Fetch Records")
        await self.fetch_records(corporateKey)
        # print("Uploading hierarchy")
        await self.disconnect()

    @cherrypy.expose
    def part2_fetch(self, corporateKey):
        asyncio.run(self.part2_fetch_routine(
            corporateKey))

    async def check_db(self):
        # check how many records are in each table of the database, save them to a dictionary
        table_count = {}
        table_count["user"] = await self.prisma.user.count()
        table_count["server"] = await self.prisma.server.count()
        table_count["application"] = await self.prisma.application.count()
        table_count["requests"] = await self.prisma.requests.count()
        table_count["corporatekey"] = await self.prisma.corporatekey.count()

        return table_count

    async def part3_check_db(self):
        # print("Connecting to database")
        await self.connect()
        # print("Check All Records")
        counts = await self.check_db()
        # print("Uploading hierarchy")
        await self.disconnect()

        return counts

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def part3_check(self):
        return asyncio.run(self.part3_check_db())


if __name__ == '__main__':
    cherrypy.quickstart(MainServer())
