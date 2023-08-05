
import os
import time
import json
import signal
import requests
import concurrent.futures
import threading
import sys

class PlayFabServer:
    def __init__(self, title_id, secret_key):
        self.title_id = title_id
        self.secret_key = secret_key
        self.base_url = f"https://{title_id}.playfabapi.com"
        self.cancelled = False
        self.allPlayerProfiles = []
        self.lock = threading.Lock()
        self.save_complete = False
        
    def save_to_file(self, data, path):
        directory = os.path.dirname(path)
        os.makedirs(directory, exist_ok=True)
        json_string = json.dumps(data, indent=4)
        stripped_lines = [line.strip() for line in json_string.splitlines()]
        formatted_content = '\n'.join(stripped_lines)
        formatted_content = json.loads(formatted_content)
        with open(path, 'w') as file:
            json.dump(formatted_content, file, indent=4)

        print(f"\n[+] Array saved to: {path}")


    def send_request(self, endpoint, method="POST", data=None):
        response = requests.request(method, str(self.base_url + endpoint), headers={
            "Content-Type": "application/json",
            "X-SecretKey": self.secret_key
        }, json=data)
        return response

    def getPlayerPage(self, segment_id):
        if self.cancelled:
            exit()
            return

        continuation_token = None
        while True:
            data = {
                "SegmentId": segment_id,
                "MaxBatchSize": 10000,
                "SecondsToLive": 300
            }

            if continuation_token:
                data["ContinuationToken"] = continuation_token

            response = self.send_request(endpoint="/Admin/GetPlayersInSegment", data=data)
            if response.status_code == 200:
                result = json.loads(response.text)["data"]
                player_profiles = result["PlayerProfiles"]

                for profile in player_profiles:
                    player_id = profile['PlayerId']
                    if player_id not in [p['PlayerId'] for p in self.allPlayerProfiles]:
                        self.allPlayerProfiles.append(profile)

                continuation_token = result.get("ContinuationToken")
                if not continuation_token:
                    break
            else:
                print("[-] Error Grabbing All Players. Try debugging")
                break

    def player_chuck(self, chunk): # WIP
        player_chuck = []
        for profile in chunk:
            playerChunk = self.beautify_json(profile)
            player_chuck.append(playerChunk)
        return player_chuck
    
    def beautify_json(self, data):
        return json.dumps(data, indent=4)

if __name__ == "__main__":
    title_id = input("[+] TitleId » ")
    secret_key = input("[+] SecretKey » ")
    savefilepath = input("[+] Enter Folder (to save in) » ")
    PFC = PlayFabServer(title_id, secret_key)

    def signal_handler(sig, frame):
        PFC.cancelled = True

    signal.signal(signal.SIGINT, signal_handler)

    save_path = f"{savefilepath}\data-{title_id}.json"

    print("========== J1X4 ==========\n\n[+] - Created by @gorillanot\n\n==========================")
    print("[+] Downloading Database...")

    AllSegments = PFC.send_request(endpoint="/Admin/GetAllSegments", data=None)
    if AllSegments.status_code == 200:
        asRes = json.loads(AllSegments.text)
        if "Segments" in asRes["data"] and any(segment["Name"] == "All Players" for segment in asRes["data"]["Segments"]):
            APSID = next((segment for segment in asRes["data"]["Segments"] if segment["Name"] == "All Players"), None)  # APSID = All Players Segment Id
            print("[+] AID: " + str(APSID["Id"]))
            PFC.getPlayerPage(APSID["Id"])

            PlayerProfiles = PFC.allPlayerProfiles
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = []
                chunk_size = 1000
                num_chunks = (len(PlayerProfiles) + chunk_size - 1) // chunk_size
                for i in range(num_chunks):
                    if PFC.cancelled:
                        PFC.cancelled = False
                        break

                    chunk = PlayerProfiles[i * chunk_size : (i + 1) * chunk_size]
                    future = executor.submit(PFC.player_chuck, chunk)
                    futures.append(future)

                concurrent.futures.wait(futures)

            if PFC.cancelled:
                print("[+] Saving process cancelled.") # small wip
            else:
                beautified_profiles = []
                for future in futures:
                    beautified_profiles.extend(future.result())
                
                PFC.save_to_file(beautified_profiles, save_path)
                print("[+] Saving process complete -> " + str(save_path))
                
        else:
            print("[-] Possible Segment Error.")
    else:
        print(f"[-] ({AllSegments.status_code}) Something went wrong whilst sending the request (Invalid Request) :-(")
    sys.stdout.flush()
    print("[>] Done.")
