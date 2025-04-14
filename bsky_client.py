import asyncio
import logging
from typing import Optional
from datetime import datetime, timezone

import aiohttp

from exceptions import *


class Client:
    BASE_URL = "https://bsky.social/xrpc"

    def __init__(self, http_session: aiohttp.ClientSession):
        self.http_session = http_session
        self.session = None
        self.logger = logging.getLogger("bsky_client")


    async def login(self, identifier: str, password: str) -> None:
        url = f"{self.BASE_URL}/com.atproto.server.createSession"
        async with self.http_session.post(url, json={"identifier": identifier, "password": password}) as response:
            data = await response.json()
            try:
                if "active" in data and not data["active"]:
                    if data.get("status"):
                        raise Exception(f"Account {data["handle"]} is {data.get("status")}")
                
                self.session = data
                self.session_creation_dt = datetime.now()
                self.logger.debug(f"Successfully authenticated ({data["handle"]} profile)")
            except:
                raise Exception(f"Failed to authenticate for unknown reason. Response body:\n {data}")


    async def refresh_session(self) -> None:
        url = f"{self.BASE_URL}/com.atproto.server.refreshSession"
        headers = {"Authorization": f"Bearer {self.session["refreshJwt"]}"}
        async with self.http_session.post(url, headers=headers) as response:
            data = await response.json()
            try:
                if "active" in data and not data["active"]:
                    if data.get("status"):
                        raise Exception(f"Account {data["handle"]} is {data.get("status")}")
                
                self.session = data
                self.session_creation_dt = datetime.now()
                self.logger.debug(f"Successfully refreshed session for ({self.session["handle"]} profile)")
            except:
                raise Exception(f"Failed to refreshed session for unknown reason. Response body:\n {data}")


    async def get_profile_posts(self, profile_handle: str, limit: int = 50) -> dict:
        await self.check_session()
        url = f"{self.BASE_URL}/app.bsky.feed.getAuthorFeed"
        headers = {"Authorization": f"Bearer {self.session["accessJwt"]}"}
        params = {"actor": profile_handle, "limit": limit}
        async with self.http_session.get(url, headers=headers, params=params) as response:
            await self.raise_for_status(response)
            self.logger.debug(f"Fetched {profile_handle}'s posts")
            return await response.json()


    async def get_profile_followers(self, 
                profile_handle: str, 
                limit: int = 50, 
                cursor: Optional[str] = None) -> dict:
        await self.check_session()
        url = f"{self.BASE_URL}/app.bsky.graph.getFollowers"
        headers = {"Authorization": f"Bearer {self.session["accessJwt"]}"}
        params = {"actor": profile_handle, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        async with self.http_session.get(url, headers=headers, params=params) as response:
            await self.raise_for_status(response)
            self.logger.debug(f"Fetched {profile_handle}'s followers")
            return await response.json()


    async def like(self, post_uri: str, post_cid: str) -> dict:
        await self.check_session()
        url = f"{self.BASE_URL}/com.atproto.repo.createRecord"
        headers = {"Authorization": f"Bearer {self.session["accessJwt"]}"}
        json_payload = {
            "collection": "app.bsky.feed.like",
            "repo": self.session["did"],
            "record": {
                "$type": "app.bsky.feed.like",
                "subject": {
                    "uri": post_uri,
                    "py_type": 'com.atproto.repo.strongRef',
                    "cid": post_cid
                },
                "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            }
        }
        async with self.http_session.post(url, headers=headers, json=json_payload) as response:
            await self.raise_for_status(response)
            self.logger.debug(f"Liked post (uri: {post_uri})")
            return await response.json()


    async def follow(self, profile_did: str) -> dict:
        await self.check_session()
        url = f"{self.BASE_URL}/com.atproto.repo.createRecord"
        headers = {"Authorization": f"Bearer {self.session["accessJwt"]}"}
        json_payload = {
            "collection": "app.bsky.graph.follow",
            "repo": self.session["did"],
            "record": {
                "$type": "app.bsky.graph.follow",
                "subject": profile_did,
                "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            }
        }
        async with self.http_session.post(url, headers=headers, json=json_payload) as response:
            await self.raise_for_status(response)
            self.logger.debug(f"Followed profile (did: {profile_did})")
            return await response.json()


    async def check_session(self) -> None:
        session_age = datetime.now() - self.session_creation_dt
        if session_age.seconds > 7000:
            await self.refresh_session()


    async def raise_for_status(self, response):
        if response.status >= 400:
            body = await response.json()
            message = body.get('message') if body else None
            match response.status:
                case 400:
                    raise BadRequestException(message)
                case 429:
                    raise TooManyRequestsException()
                case _:
                    raise HttpException(response.status, message)
