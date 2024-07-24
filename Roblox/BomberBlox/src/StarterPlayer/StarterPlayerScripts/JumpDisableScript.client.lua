local Players = game:GetService("Players")
local player = Players.LocalPlayer

local function disableJump(character)
	local humanoid = character:WaitForChild("Humanoid")
	humanoid.JumpPower = 0
	humanoid.JumpHeight = 0
end

if player.Character then
	disableJump(player.Character)
end

player.CharacterAdded:Connect(disableJump)