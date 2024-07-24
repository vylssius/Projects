-- Services --
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local ServerStorage = game:GetService("ServerStorage")
local Players = game:GetService("Players")

-- Variables --
local bombModel = ReplicatedStorage:WaitForChild("Bomb")
local rangePowerup = ReplicatedStorage:WaitForChild("RangePowerup")
local ghostPowerup = ReplicatedStorage:WaitForChild("GhostPowerup")
local remoteEvents = ReplicatedStorage:WaitForChild("Remote Events")
local remoteFunctions = ReplicatedStorage:WaitForChild("Remote Functions")
local explosionSound = ServerStorage:WaitForChild("ExplosionSound")

-- Events --
local placeBombEvent = remoteEvents:WaitForChild("PlaceBombEvent")
local bombExplodedEvent = remoteEvents:WaitForChild("BombExplodedEvent")

-- Remote Functions --
local getRangePowerupCount = remoteFunctions:WaitForChild("GetRangePowerupCount")
local hasGhostPowerup = remoteFunctions:WaitForChild("HasGhostPowerup")

-- Functions --
local function getFloorBelow(position, ignoreList)
	local ray = Ray.new(position, Vector3.new(0, -50, 0))
	local raycastParams = RaycastParams.new()
	raycastParams.FilterType = Enum.RaycastFilterType.Exclude
	raycastParams.FilterDescendantsInstances = ignoreList

	local raycastResult = workspace:Raycast(position, Vector3.new(0, -50, 0), raycastParams)
	if raycastResult then
		return raycastResult.Instance, raycastResult.Position
	else
		return nil, nil
	end
end

local function spawnExplosion(position)
	local explosion = Instance.new("Explosion")
	explosion.Position = position
	explosion.BlastRadius = 1
	explosion.BlastPressure = 5000
	explosion.Parent = workspace:WaitForChild("Arena")

	explosion.Hit:Connect(function(hit)
		if hit.Parent:FindFirstChild("Humanoid") then
			hit.Parent.Humanoid:TakeDamage(100)
		elseif hit:IsA("Part") and hit.Name == "BreakableBlock" then
			hit:Destroy()
			local randomNumber = math.random(0, 101)

			if randomNumber < 5 then
				local powerup = ghostPowerup:Clone()
				powerup.Position = hit.Position
				powerup.Parent = workspace:WaitForChild("Arena")
			elseif randomNumber > 5 and randomNumber < 20 then
				local powerup = rangePowerup:Clone()
				powerup.Position = hit.Position
				powerup.Parent = workspace:WaitForChild("Arena")
			end
		end
	end)
end

local function getRangePowerupCountFromPlayer(player)
	local success, bombRange = pcall(function()
		return getRangePowerupCount:InvokeClient(player)
	end)

	if success then
		return bombRange
	else
		warn("Failed to get bomb range from player")
		return nil
	end
end

local function hasGhostPowerupFromPlayer(player)
	local success, hasGhost = pcall(function()
		return hasGhostPowerup:InvokeClient(player)
	end)

	if success then
		return hasGhost
	else
		warn("Failed to check for ghost powerup on player")
		return false -- Default to false if check fails
	end
end

local function checkDirectionAndExplode(startPosition, direction, bomb, placer)
	local explosionRange = getRangePowerupCountFromPlayer(placer)
	local explosionAdjustedRange = 1 + explosionRange
	local hasGhostPowerup = hasGhostPowerupFromPlayer(placer)
	local blockLength = 4
	print(hasGhostPowerup)

	for i = 1, explosionAdjustedRange do
		local explosionPosition = startPosition + direction * (2.5 + blockLength * i)
		local ray = Ray.new(startPosition, direction * (blockLength * i))
		local hit = workspace:FindPartOnRayWithIgnoreList(ray, { bomb })

		spawnExplosion(explosionPosition)

		if hit then
			if hit:IsA("Part") then
				if hit.Name == "BreakableBlock" then
					local hitPosition = hit.Position
					local randomNumber = math.random(0, 101)
					spawnExplosion(hitPosition)
					hit:Destroy()

					if randomNumber < 5 then
						local powerup = ghostPowerup:Clone()
						powerup.Position = hit.Position
						powerup.Parent = workspace:WaitForChild("Arena")
						break
					elseif randomNumber > 5 and randomNumber < 20 then
						local powerup = rangePowerup:Clone()
						powerup.Position = hit.Position
						powerup.Parent = workspace:WaitForChild("Arena")
						break
					end

					if not hasGhostPowerup then
						break
					end
				elseif hit.Name == "UnbreakableBlock" then
					break
				elseif hit.Name == ghostPowerup.Name or hit.Name == rangePowerup.Name then
					hit:Destroy()
					break
				end
			elseif hit.Parent:FindFirstChild("Humanoid") then
				hit.Parent.Humanoid:TakeDamage(100)
				break
			else
				spawnExplosion(explosionPosition)
			end
		else
			spawnExplosion(explosionPosition)
		end
	end
end

local function explodeBomb(bomb, placer)
	local bombPrimaryPart = bomb.PrimaryPart
	if not bombPrimaryPart then
		warn("Bomb does not have a primary part")
		return
	end

	local directions = {
		Vector3.new(1, 0, 0), -- Right
		Vector3.new(-1, 0, 0), -- Left
		Vector3.new(0, 0, 1), -- Forward
		Vector3.new(0, 0, -1), -- Backward
	}

	local coroutines = {}

	-- Create a coroutine for each direction
	for _, direction in ipairs(directions) do
		local co = coroutine.create(function()
			checkDirectionAndExplode(bombPrimaryPart.Position, direction, bomb, placer)
		end)
		table.insert(coroutines, co)
	end

	-- Resume each coroutine
	for _, co in ipairs(coroutines) do
		coroutine.resume(co)
	end

	local sound = explosionSound:Clone()
	sound.Parent = workspace
	sound:Play()
	sound.Ended:Connect(function()
		sound:Destroy()
	end)

	spawnExplosion(bombPrimaryPart.Position)
	bomb:Destroy()
end

local function placeBomb(player)
	local character = player.Character
	if not character then
		return
	end
	local primaryPart = character.PrimaryPart
	if not primaryPart then
		return
	end

	local floorPart, hitposition = getFloorBelow(primaryPart.Position, { character })
	if not floorPart then
		return
	end

	local bomb = bombModel:Clone()
	local bombPrimaryPart = bomb:FindFirstChild("PrimaryPart")

	if not bombPrimaryPart then
		warn("Bomb model has no primary part!")
		return
	end

	bomb.PrimaryPart = bombPrimaryPart

	-- Unanchor all parts in the bomb model
	for _, part in ipairs(bomb:GetDescendants()) do
		if part:IsA("BasePart") then
			part.Anchored = false
		end
	end

	local centerPosition = floorPart.Position
	bomb:SetPrimaryPartCFrame(
		CFrame.new(centerPosition + Vector3.new(0, floorPart.Size.Y / 2 + bombPrimaryPart.Size.Y / 2, 0))
	)
	bomb.Parent = workspace

	-- Re-anchor all parts in the bomb model
	for _, part in ipairs(bomb:GetDescendants()) do
		if part:IsA("BasePart") then
			part.Anchored = true
		end
	end

	-- Disable collision function
	local function disableCollisions()
		for _, part in ipairs(bomb:GetDescendants()) do
			if part:IsA("BasePart") then
				part.CanCollide = false
			end
		end
	end

	local function enableCollisions()
		for _, part in ipairs(bomb:GetDescendants()) do
			if part:IsA("BasePart") then
				part.CanCollide = true
			end
		end
	end

	-- Check if player is inside the bomb
	local function checkPlayerInside()
		local playerPosition = character.PrimaryPart.Position
		local bombPosition = bombPrimaryPart.Position
		local distance = (playerPosition - bombPosition).Magnitude
		return distance < bombPrimaryPart.Size.X
	end

	disableCollisions()

	local connection
	connection = game:GetService("RunService").Stepped:Connect(function()
		if not checkPlayerInside() then
			enableCollisions()
			connection:Disconnect()
		end
	end)

	wait(3)

	explodeBomb(bomb, player)
end

placeBombEvent.OnServerEvent:Connect(placeBomb)
