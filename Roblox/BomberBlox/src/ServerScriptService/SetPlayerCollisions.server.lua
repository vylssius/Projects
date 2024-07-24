-- Services --
local Players = game:GetService("Players")
local PhysicsService = game:GetService("PhysicsService")

-- Functions --
local function onCharacterAdded(character)
	for _, part in ipairs(character:GetDescendants()) do
		if part:IsA("BasePart") then
			part.CollisionGroup = "Players"
		end
	end
end

local function onPlayerAdded(player)
	player.CharacterAdded:Connect(onCharacterAdded)
	if player.Character then
		onCharacterAdded(player.Character)
	end
end

Players.PlayerAdded:Connect(onPlayerAdded)

-- For existing players when script is first run
for _, player in ipairs(Players:GetPlayers()) do
	onPlayerAdded(player)
end