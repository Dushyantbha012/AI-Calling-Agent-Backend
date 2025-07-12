import os
from twilio.rest import Client
import asyncio
from logger_config import get_logger

logger = get_logger("TransferCall")

async def transfer_call(context, args):
    # Retrieve the active call using the CallSid
    account_sid = os.environ['TWILIO_ACCOUNT_SID']
    auth_token = os.environ['TWILIO_AUTH_TOKEN']
    transfer_number = os.environ['TRANSFER_NUMBER']

    client = Client(account_sid, auth_token)
    call_sid = context.call_sid
    
    logger.info(f"Preparing to transfer call with SID: {call_sid} to number: {transfer_number}")

    # Wait for 8 seconds before transferring the call
    logger.info("Waiting 8 seconds before transferring call...")
    await asyncio.sleep(8)

    try:
        call = client.calls(call_sid).fetch()
        
        # Update the call with the transfer number
        logger.info(f"Transferring call to: {transfer_number}")
        call = client.calls(call_sid).update(
            url=f'http://twimlets.com/forward?PhoneNumber={transfer_number}',
            method='POST'
        )
            
        logger.info("Call transferred successfully")
        return f"Call transferred successfully to {transfer_number}."

    except Exception as e:
        logger.error(f"Error transferring call: {str(e)}")
        return f"Error transferring call: {str(e)}"