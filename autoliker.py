import asyncio
import logging
import random

from bsky_client import Client


class Autoliker:
    def __init__(self, client: Client, handle: str, password: str):
        self.client = client
        self.handle = handle
        self.password = password

        self.total_likes = 0
        self.total_followings = 0

        self.logger = logging.getLogger(self.handle)


    async def run(self, profiles: list[str], processed_profiles: list[str]):
        await self.client.login(self.handle, self.password)
        self.logger.info(f"Successfully authorised!")

        for pfl in profiles:
            cursor = None

            while True:
                try:
                    followers_response = await self.client.get_profile_followers(pfl, 100, cursor)
                    cursor = followers_response.get("cursor")

                    for follower_data in followers_response['followers']:
                        if follower_data["handle"].replace('.bsky.social', '') in processed_profiles:
                            continue

                        res = await self._process_follower(follower_data)
                        processed_profiles.append(follower_data["handle"].replace('.bsky.social', ''))

                        if res:
                            wait_time = random.uniform(7, 11)
                            await asyncio.sleep(wait_time)

                    if not cursor:
                        break
                except TooManyRequestsException:
                    # BlueSky does not add 'Retry-After' header
                    wait_time = 300
                    self.logger.error(f"Got '429 Too Many Requests' Error. Sleeping for {wait_time} s...")
                    await asyncio.sleep(wait_time)
                except BadRequestException as ex:
                    self.logger.error(f"Got '400 Bad Requests' Error!\n{ex}")
                except HttpException as ex:
                    self.logger.error(f"Got an error with status code {ex.status_code}!\n{ex}")
                    await asyncio.sleep(15)

        self.logger.warning("Processing profiles completed!")


    async def _process_follower(self, follower_data: dict) -> bool:
        if Autoliker._has_bad_links(follower_data.get("description", "")):
            self.logger.info(f"Found bad links in profile {follower_data["handle"]}")
            return False

        for attempts in range(3):
            try:
                posts_response = await self.client.get_profile_posts(follower_data['did'], 1)

                if 'feed' not in posts_response:
                    return False

                if posts_response['feed']:
                    latest_post = posts_response['feed'][0]['post']
                    await self.client.like(latest_post['uri'], latest_post['cid'])
                    self.total_likes += 1
                    self.logger.info(f"Liked a post in {follower_data["handle"]}")
                else:
                    await self.client.follow(follower_data['did'])
                    self.total_followings += 1
                    self.logger.info(f"Followed profile {follower_data["handle"]}")

                return True
            except BadRequestException as ex:
                self.logger.warning(f"Got '400 Bad Response' Error while interacting with {follower_data["handle"]} profile.\n{ex}")
                return False
            except TooManyRequestsException:
                # BlueSky does not add 'Retry-After' header
                wait_time = 300
                self.logger.error(f"Got '429 Too Many Requests' Error. Sleeping for {wait_time} s...")
                await asyncio.sleep(wait_time)
            except HttpException as ex:
                self.logger.error(f"Got an error with status code {ex.status_code} while interacting with {follower_data["handle"]} profile.\n{ex}")
                await asyncio.sleep(15)


    @staticmethod
    def _has_bad_links(description: str) -> bool:
        bad_links = ["onlyfans.com", "fansly.com"]
        return any(link in description for link in bad_links)
