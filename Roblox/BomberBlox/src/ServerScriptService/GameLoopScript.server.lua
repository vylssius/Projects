-- Services --
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local ServerStorage = game:GetService("ServerStorage")

-- Variables
local preLobbySpawn = workspace.PreGameLobby:FindFirstChild("PreLobbySpawn") -- Assuming you have a spawn location for the pre-lobby
local remoteEvents = ReplicatedStorage:WaitForChild("Remote Events")
local remoteFunctions = ReplicatedStorage:WaitForChild("Remote Functions")

-- Maps --
local ChaosMap = ServerStorage:WaitForChild("ChaosMap")
local DuelMap = ServerStorage:WaitForChild("DuelMap")

-- Events --
local countdownEvent = remoteEvents:WaitForChild("CountdownEvent")
local waitingEvent = remoteEvents:WaitForChild("WaitingEvent")
local powerupPickupEvent = remoteEvents:WaitForChild("PowerupPickupEvent")
local winnerEvent = remoteEvents:WaitForChild("WinnerEvent")

-- Remote Functions --
local checkPlayerInArena = remoteFunctions:WaitForChild("CheckPlayerInArena")
local clearPowerups = remoteFunctions:WaitForChild("ClearPowerups")

-- Variables --
local minPlayers = 2
local gameInProgress = false
playersInArena = {}
currentMap = ChaosMap

-- Functions --
local function onPlayerDeath(player)
	-- Remove the player from the playersInArena table
	for i, otherPlayer in ipairs(playersInArena) do
		if otherPlayer == player then
			table.remove(playersInArena, i)
			break
		end
	end

	-- Reset Powerups
	clearPowerups:InvokeClient(player)
end

local function onPlayerAdded(player)
	player.CharacterAdded:Connect(function(character)
		character:SetPrimaryPartCFrame(preLobbySpawn.CFrame)
	end)
end

local function checkPowerupDistance(player, powerup)
	if not powerup or not powerup:IsA("BasePart") then
		return
	end
	local character = player.Character
	if not character or not character.PrimaryPart then
		return
	end
	local playerPosition = character.PrimaryPart.Position
	local powerupPosition = powerup.Position
	local distance = (playerPosition - powerupPosition).Magnitude

	if distance <= powerup.Size.X then
		print("Powerup Picked Up")
		local powerupName = powerup.Name
		powerupPickupEvent:FireClient(player, powerupName) -- Tell client they picked up a power up
		powerup:Destroy()
	end
end

local function checkPowerupPickup()
	-- Check if any player has picked up a powerup
	while gameInProgress do
		for _, player in ipairs(playersInArena) do
			local character = player.Character
			if character then
				for _, powerup in gameMap:GetChildren() do
					if powerup.Name == "RangePowerup" then
						checkPowerupDistance(player, powerup)
					elseif powerup.Name == "GhostPowerup" then
						checkPowerupDistance(player, powerup)
					end
				end
			end
		end
		wait(0.3)
	end
end

local function spawnMap()
	local delayTime = 0.01
	local partsPerBatch = 10 -- Number of parts to spawn per batch
	local mapLoadingComplete = Instance.new("BindableEvent")
	local coroutines = {} -- To keep track of all coroutines
	local completedCoroutines = 0

	local function createFolderStructure(folder, parent, isTopLevel)
		local newFolder = Instance.new("Folder")
		newFolder.Name = isTopLevel and "Arena" or folder.Name
		newFolder.Parent = parent

		local partsToSpawn = {}

		for _, item in ipairs(folder:GetChildren()) do
			if item:IsA("Folder") then
				createFolderStructure(item, newFolder, false)
			elseif item:IsA("BasePart") then
				table.insert(partsToSpawn, { block = item, parent = newFolder })
			end
		end

		local function spawnParts(parts)
			for _, partInfo in ipairs(parts) do
				local clonedBlock = partInfo.block:Clone()
				clonedBlock.Parent = partInfo.parent
				clonedBlock.Position = partInfo.block.Position
			end
		end

		local co = coroutine.wrap(function()
			for i = 1, #partsToSpawn, partsPerBatch do
				local batch = {}
				for j = i, math.min(i + partsPerBatch - 1, #partsToSpawn) do
					table.insert(batch, partsToSpawn[j])
				end
				spawnParts(batch)
				RunService.Heartbeat:Wait()
			end
			completedCoroutines = completedCoroutines + 1
			if completedCoroutines == #coroutines then
				print("Map loading complete, firing event")
				mapLoadingComplete:Fire()
			end
		end)

		table.insert(coroutines, co)
	end

	-- Start by creating the top-level folder structure directly in the workspace
	createFolderStructure(currentMap, workspace, true)

	-- Resume all coroutines
	for _, co in ipairs(coroutines) do
		co()
	end

	return mapLoadingComplete.Event
end

local function startGame()
	gameMap = workspace:FindFirstChild("Arena")
	gameMap.ChildAdded:Connect(function(child)
		-- Check for powerups
		if child.Name == "RangePowerup" then
			print("New powerup added: " .. child.Name)
			for _, player in ipairs(playersInArena) do
				checkPowerupDistance(player, child)
			end
		elseif child.Name == "GhostPowerup" then
			print("New powerup added: " .. child.Name)
			for _, player in ipairs(playersInArena) do
				checkPowerupDistance(player, child)
			end
		end
	end)

	wait(1)

	local gameArenaSpawns = gameMap.GameArenaSpawns:GetChildren()

	for _, player in ipairs(Players:GetPlayers()) do
		-- Add the player to the playersInArena table
		table.insert(playersInArena, player)

		-- Teleport the player to the game arena
		local spawnLocation = gameArenaSpawns[math.random(1, #gameArenaSpawns)]
		player.Character:SetPrimaryPartCFrame(spawnLocation.CFrame)
		player.Character.Humanoid.Died:Connect(function()
			onPlayerDeath(player)
		end)
	end

	spawn(checkPowerupPickup) -- Start powerup checking in a separate thread
	gameInProgress = true
end

local function endGame()
	gameInProgress = false

	for _, player in ipairs(playersInArena) do
		player.Character:SetPrimaryPartCFrame(preLobbySpawn.CFrame)
		clearPowerups:InvokeClient(player)
	end

	playersInArena = {}
	gameMap:Destroy()
end

-- Connect functions --
Players.PlayerAdded:Connect(onPlayerAdded)
Players.PlayerRemoving:Connect(function(player)
	if gameInProgress then
		for _, otherplayer in ipairs(playersInArena) do
			if otherplayer == player then
				table.remove(playersInArena, otherplayer)
				break
			end
		end
	end
end)

checkPlayerInArena.OnServerInvoke = function(player, bool)
	for _, otherplayer in ipairs(playersInArena) do
		if otherplayer == player then
			return true
		end
	end
	return false
end

-- Game Loop --
while true do
	wait(5) -- Wait a bit before starting the next iteration of the loop

	-- Wait for the minimum number of players to join
	while #Players:GetPlayers() < minPlayers do
		print("Waiting for players...")
		waitingEvent:FireAllClients() -- Notify clients that we are waiting for players
		wait(1)
	end

	-- 10 second countdown
	for i = 10, 0, -1 do
		if #Players:GetPlayers() < minPlayers then -- Check if player count drops below minPlayers during countdown
			print("Not enough players, countdown cancelled.")
			waitingEvent:FireAllClients() -- Notify clients that countdown is cancelled
			break -- Exit the countdown loop
		end
		countdownEvent:FireAllClients(i) -- Update clients with the current countdown number
		wait(1)
	end

	if #Players:GetPlayers() < minPlayers then
		continue -- Skip the rest of the current iteration of the loop and start waiting for players again
	end

	-- Load Map
	print("Waiting for map")
	local mapLoadingCompleteEvent = spawnMap()
	mapLoadingCompleteEvent:Wait() -- Wait until the map loading is done
	print("Map loading complete, starting game")

	-- Start game
	startGame()

	-- Keep game running until only 1 player remains
	while #playersInArena > 1 do
		wait(1)
	end

	-- Display winner message to everyone
	if #playersInArena == 1 then -- loop check if player alive spawn win message
		wait(3)
		local winner = playersInArena[1]
		winnerEvent:FireAllClients(winner.Name)
	else
		wait(3)
		winnerEvent:FireAllClients("Nobody")
	end

	wait(3)

	-- End game
	endGame()
end
