import asyncio
import logging
import json

import aiohttp
from aiohttp_socks import ProxyConnector
import coloredlogs

from bsky_client import Client
from autoliker import Autoliker


logging.getLogger("asyncio").setLevel(logging.WARNING)

coloredlogs.install(
    level=logging.INFO, 
    fmt="%(asctime)s %(name)s: %(message)s", 
    datefmt='%I:%M:%S')


def read_proxies() -> list[str]:
    with open("proxies.txt", "r") as file:
        return [line for line in file.read().splitlines() if not line.startswith('#')]


def read_credentials() -> list[tuple[str, str]]:
    with open("credentials.txt", "r") as file:
        return [tuple(line.strip().split(";", 1)) for line in file]


def read_base_profiles() -> list[str]:
    with open("profiles.txt", "r") as file:
        return file.read().splitlines()


def read_processed_profiles() -> dict[str, list[str]]:
    try:
        with open("processed_profiles.json", "r") as file:
            return json.load(file)
    except:
        return {}


def save_processed_profiles(data: dict[str, list[str]]):
    with open("processed_profiles.json", "w") as file:
        json.dump(data, file, indent=4)


def chunk_list(lst: list, n: int) -> list[list]:
    k, m = divmod(len(lst), n)
    return [lst[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n)]


async def main():
    credentials = read_credentials()
    profiles = read_base_profiles()
    processed_profiles = read_processed_profiles()

    proxies = read_proxies()
    if not proxies:
        print("No proxies were found")
        exit()

    proxy_connectors = [ProxyConnector.from_url(proxy) for proxy in proxies]
    sessions = [aiohttp.ClientSession(connector=pc) for pc in proxy_connectors]
    clients = [Client(sessions[i % len(sessions)]) for i in range(len(credentials))]
    likers = [Autoliker(client, *creds) for client, creds in zip(clients, credentials)]
    
    try:
        chunked_profiles = chunk_list(profiles, len(likers))
        tasks = []
        for liker, pfls in zip(likers, chunked_profiles):
            account_name = liker.handle.replace('.bsky.social', '')
            if account_name not in processed_profiles:
                processed_profiles[account_name] = []
            tasks.append(liker.run(pfls, processed_profiles[account_name]))

        await asyncio.gather(*tasks)
    finally:
        for liker in likers:
            print(f"\n{liker.handle} liked {liker.total_likes} posts")
            print(f"{liker.handle} followed {liker.total_followings} profiles")
        save_processed_profiles(processed_profiles)
        for session in sessions:
            await session.close()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram terminated by user.")
