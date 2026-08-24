namespace ImportRaceEntries.Netkeiba.Models {
    public sealed class NetkeibaRaceHeaderRaw {
        public Guid ImportBatchId { get; set; }
        public string RaceId { get; set; } = string.Empty;

        public string? RaceNoRaw { get; set; }
        public string? RaceDateRaw { get; set; }
        public string? RaceNameRaw { get; set; }
        public string? TrackNameRaw { get; set; }
        public string? SurfaceDistanceRaw { get; set; }

        public string MeetingRaw { get; set; } = string.Empty;
        public string TurnRaw { get; set; } = string.Empty;
        public string RaceClassRaw { get; set; } = string.Empty;
        public string HeadCountRaw { get; set; } = string.Empty;

        public string StartTimeRaw { get; set; } = string.Empty;
        public string TurnDirRaw { get; set; } = string.Empty;
        public string CourseRingRaw { get; set; } = string.Empty;
        public string CourseExRaw { get; set; } = string.Empty;
        public string CourseDetailRaw { get; set; } = string.Empty;

        public string SurfaceTypeRaw { get; set; } = string.Empty;
        public string DistanceMRaw { get; set; } = string.Empty;

        public DateTime ScrapedAt { get; set; }
        public string? SourceUrl { get; set; }
        public string? SourceFile { get; set; }
        public DateTime CreatedAt { get; set; }
    }

    public sealed class NetkeibaRaceEntryRowRaw {
        public Guid ImportBatchId { get; set; }
        public int RowNo { get; set; }

        public string? NkHorseId { get; set; }
        public string? JvHorseId { get; set; }

        public string? FrameNoRaw { get; set; }
        public string? HorseNoRaw { get; set; }
        public string? HorseNameRaw { get; set; }
        public string? SexAgeRaw { get; set; }
        public string? JockeyNameRaw { get; set; }
        public string? CarriedWeightRaw { get; set; }
    }
}
