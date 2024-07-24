-- Services --
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Players = game:GetService("Players")
local UIS = game:GetService("UserInputService")

-- Variables --
local player = Players.LocalPlayer
local bombPlaced = false
local bombRange = 0
local ghostPowerup = false
local remoteEvents = ReplicatedStorage:WaitForChild("Remote Events")
local remoteFunctions = ReplicatedStorage:WaitForChild("Remote Functions")

-- Events --
local placeBombEvent = remoteEvents:WaitForChild("PlaceBombEvent")
local powerupPickupEvent = remoteEvents:WaitForChild("PowerupPickupEvent")

-- Remote Functions --
local checkPlayerInArena = remoteFunctions:WaitForChild("CheckPlayerInArena")
local getRangePowerupCount = remoteFunctions:WaitForChild("GetRangePowerupCount")
local clearPowerups = remoteFunctions:WaitForChild("ClearPowerups")
local hasGhostPowerup = remoteFunctions:WaitForChild("HasGhostPowerup")


-- Functions --
local function setupInputHandling()
	UIS.InputBegan:Connect(function(input, gameProcessedEvent)
		if gameProcessedEvent then return end
		if input.KeyCode == Enum.KeyCode.Space and not bombPlaced then
			local inArena = checkPlayerInArena:InvokeServer(false)
			if inArena == true then
				bombPlaced = true
				placeBombEvent:FireServer()
				print("Bomb Event Fired")
				print(bombRange)
				wait(3)
				bombPlaced = false
			end
		end
	end)
end

local function powerupObtained(powerupName)
	if powerupName == "RangePowerup" then
		bombRange += 1
		print("Powerup obtained: " .. powerupName .. ", new bomb range: " .. bombRange)
	elseif powerupName == "GhostPowerup" then
		if not ghostPowerup then
			ghostPowerup = true
			print("Powerup obtained: " .. powerupName .. ", ghost mode enabled.")
		else
			return
		end
	end
end

local function onGetRangePowerupCount()
	return bombRange
end

local function onHasGhostPowerup()
	return ghostPowerup
end

local function onClearPowerups()
	-- Reset bomb range
	bombRange = 0
end

-- Remote Event Calls --
powerupPickupEvent.OnClientEvent:Connect(powerupObtained)

-- Remote Function Calls --
getRangePowerupCount.OnClientInvoke = onGetRangePowerupCount
clearPowerups.OnClientInvoke = onClearPowerups
hasGhostPowerup.OnClientInvoke = onHasGhostPowerup

-- Function Calls --
setupInputHandling()