using ASA.ServerManager.Infrastructure;

namespace ASA.ServerManager.Tests;

public sealed class RconPacketCodecTests
{
    [Fact]
    public async Task WriteAsync_UsesLittleEndianSizeIdAndType()
    {
        await using MemoryStream stream = new MemoryStream();
        await RconPacketCodec.WriteAsync(stream, new RconPacket(7, 2, "abc"), CancellationToken.None);
        byte[] bytes = stream.ToArray();
        Assert.Equal(13, BitConverter.ToInt32(bytes, 0));
        Assert.Equal(7, BitConverter.ToInt32(bytes, 4));
        Assert.Equal(2, BitConverter.ToInt32(bytes, 8));
    }

    [Fact]
    public async Task ReadAsync_RoundTripsBody()
    {
        await using MemoryStream stream = new MemoryStream();
        await RconPacketCodec.WriteAsync(stream, new RconPacket(9, 2, "SaveWorld"), CancellationToken.None);
        stream.Position = 0;
        RconPacket packet = await RconPacketCodec.ReadAsync(stream, CancellationToken.None);
        Assert.Equal(9, packet.Id);
        Assert.Equal("SaveWorld", packet.Body);
    }

    [Fact]
    public async Task ReadAsync_RejectsTooSmallPacket()
    {
        await using MemoryStream stream = new MemoryStream(BitConverter.GetBytes(9));
        await Assert.ThrowsAsync<IOException>(async () => await RconPacketCodec.ReadAsync(stream, CancellationToken.None));
    }

    [Fact]
    public async Task ReadAsync_RejectsTooLargePacket()
    {
        await using MemoryStream stream = new MemoryStream(BitConverter.GetBytes((4 * 1024 * 1024) + 1));
        await Assert.ThrowsAsync<IOException>(async () => await RconPacketCodec.ReadAsync(stream, CancellationToken.None));
    }

    [Fact]
    public async Task ReadAsync_RejectsPrematureStreamClose()
    {
        await using MemoryStream stream = new MemoryStream(BitConverter.GetBytes(10));
        await Assert.ThrowsAsync<IOException>(async () => await RconPacketCodec.ReadAsync(stream, CancellationToken.None));
    }
}
